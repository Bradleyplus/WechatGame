import streamlit as st
import requests
import uuid
import time

# ---------------------- 页面配置与样式 ----------------------
st.set_page_config(
    page_title="双人井字棋",
    layout="centered",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    .board-container {
        width: 100% !important;
        max-width: 210px !important;
        margin: 0 auto !important;
    }
    .stButton > button {
        width: 100% !important;
        height: 60px !important;
        font-size: 1.5rem !important;
        padding: 0 !important;
        margin: 1px !important;
    }
    .debug-info {
        font-size: 0.8rem;
        color: #666;
        margin-top: 10px;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------- 云存储配置 ----------------------
APP_ID = "hiwS1jgaGdLqJhk2UtEwHGdK-gzGzoHsz"
APP_KEY = "bENg8Yr0UlGdt7NJB70i2VOW"
BASE_API_URL = "https://api.leancloud.cn/1.1/classes/GameState"
HEADERS = {
    "X-LC-Id": APP_ID,
    "X-LC-Key": APP_KEY,
    "Content-Type": "application/json"
}


# ---------------------- 核心工具函数 ----------------------
def check_winner(board):
    win_combinations = [
        [0, 1, 2], [3, 4, 5], [6, 7, 8],
        [0, 3, 6], [1, 4, 7], [2, 5, 8],
        [0, 4, 8], [2, 4, 6]
    ]
    for combo in win_combinations:
        a, b, c = combo
        if board[a] == board[b] == board[c] != "":
            return board[a]
    if "" not in board:
        return "平局"
    return None


def get_device_id():
    """设备ID永久绑定到会话（刷新/重进页面不变）"""
    if "device_id" not in st.session_state:
        # 生成唯一ID并永久保存
        st.session_state.device_id = str(uuid.uuid4())
    return st.session_state.device_id


# ---------------------- 房间管理（核心修复） ----------------------
def force_clean_room(room_id):
    try:
        params = {"where": f'{{"room_id":"{room_id}"}}', "limit": 1}
        res = requests.get(BASE_API_URL, headers=HEADERS, params=params, timeout=10)
        if res.status_code == 200 and res.json().get("results"):
            object_id = res.json()["results"][0]["objectId"]
            requests.delete(f"{BASE_API_URL}/{object_id}", headers=HEADERS, timeout=10)
            st.success(f"房间 {room_id} 清理成功！")
            time.sleep(1)
        else:
            st.info(f"房间 {room_id} 无残留记录")
    except Exception as e:
        st.error(f"清理失败：{str(e)}")


def load_room(room_id):
    """加载房间数据，确保返回完整玩家列表"""
    try:
        params = {"where": f'{{"room_id":"{room_id}"}}', "limit": 1}
        res = requests.get(BASE_API_URL, headers=HEADERS, params=params, timeout=10)
        res.raise_for_status()
        data = res.json()
        if data.get("results"):
            room_data = data["results"][0]
            # 确保玩家列表默认是空字典（避免None导致的错误）
            room_data["players"] = room_data.get("players", {})
            room_data["player_count"] = len(room_data["players"])  # 用列表长度计算人数（更准确）
            return room_data
        return None
    except Exception as e:
        st.error(f"加载房间失败：{str(e)}")
        return None


def create_room(room_id):
    """创建房间，强制写入当前设备ID"""
    device_id = get_device_id()
    init_data = {
        "room_id": room_id,
        "board": ["", "", "", "", "", "", "", "", ""],
        "current_player": "X",
        "game_over": False,
        "winner": None,
        "players": {device_id: "X"}  # 玩家列表仅包含当前设备
    }
    # 玩家数量由列表长度决定，不单独维护（避免不一致）
    init_data["player_count"] = len(init_data["players"])
    res = requests.post(BASE_API_URL, headers=HEADERS, json=init_data, timeout=10)
    res.raise_for_status()
    init_data["objectId"] = res.json()["objectId"]
    return init_data


def enter_room(room_id):
    """进入房间：严格检查设备是否已在房间中，避免重复添加/误删"""
    device_id = get_device_id()
    room_data = load_room(room_id)

    # 情况1：房间不存在，创建新房间（当前设备为X）
    if not room_data:
        return create_room(room_id)

    # 情况2：当前设备已在房间中，直接返回（核心：避免被误判为新设备）
    if device_id in room_data["players"]:
        return room_data

    # 情况3：房间未满（<2人），添加为O
    if len(room_data["players"]) < 2:
        updated_players = room_data["players"].copy()
        updated_players[device_id] = "O"  # 强制添加当前设备
        updated_data = {
            **room_data,
            "players": updated_players,
            "player_count": len(updated_players)  # 用实际长度更新人数
        }
        # 强制同步到云端（确保玩家列表被保存）
        requests.put(
            f"{BASE_API_URL}/{room_data['objectId']}",
            headers=HEADERS,
            json=updated_data,
            timeout=10
        )
        return updated_data

    # 情况4：房间已满
    return None


# ---------------------- 状态恢复与验证 ----------------------
def auto_restore_state(room_id):
    """修复：仅在设备确实不在房间时才重置状态"""
    if st.session_state.entered_room:
        room_data = load_room(room_id)
        if room_data:
            device_id = get_device_id()
            # 关键：只要设备在玩家列表中，就恢复状态（即使其他数据有变化）
            if device_id in room_data["players"]:
                st.session_state.object_id = room_data["objectId"]
                st.session_state.board = room_data.get("board", ["", "", "", "", "", "", "", "", ""])
                st.session_state.current_player = room_data.get("current_player", "X")
                st.session_state.game_over = room_data.get("game_over", False)
                st.session_state.winner = room_data.get("winner")
                st.session_state.players = room_data["players"]
                st.session_state.my_role = room_data["players"][device_id]
                return True
            else:
                # 设备确实不在房间中，才重置
                st.session_state.entered_room = False
                st.session_state.my_role = None
                st.warning("你已离开房间，请重新进入")
        else:
            # 房间不存在，重置
            st.session_state.entered_room = False
            st.session_state.my_role = None
            st.warning("房间已解散，请重新进入")
    return False


# ---------------------- 主页面逻辑 ----------------------
st.title("🎮 双人井字棋（联机版）")

# 选择房间
room_id = st.selectbox(
    "🔑 选择游戏房间",
    options=["8888", "6666"],
    index=0,
    key="room_selector"
)

# 初始化会话状态（确保核心变量有默认值）
required_states = {
    "entered_room": False,
    "my_role": None,
    "object_id": None,
    "board": ["", "", "", "", "", "", "", "", ""],
    "current_player": "X",
    "game_over": False,
    "winner": None,
    "players": {}  # 玩家列表（设备ID: 角色）
}
for key, default in required_states.items():
    if key not in st.session_state:
        st.session_state[key] = default

# 页面加载时自动恢复状态（修复：避免误判移除）
auto_restore_state(room_id)

# 紧急清理按钮
if st.button("⚠️ 强制清理房间", use_container_width=True, type="secondary"):
    force_clean_room(room_id)
    st.rerun()

# 操作按钮：刷新/退出
col_refresh, col_exit = st.columns(2)
with col_refresh:
    if st.button("🔄 手动刷新", use_container_width=True):
        auto_restore_state(room_id)
        st.success("手动刷新完成")

with col_exit:
    if st.button("🚪 退出房间", use_container_width=True) and st.session_state.entered_room:
        room_data = load_room(room_id)
        if room_data:
            device_id = get_device_id()
            players = room_data["players"].copy()
            if device_id in players:
                del players[device_id]  # 仅移除当前设备
                updated_data = {
                    **room_data,
                    "players": players,
                    "player_count": len(players)
                }
                requests.put(
                    f"{BASE_API_URL}/{room_data['objectId']}",
                    headers=HEADERS,
                    json=updated_data,
                    timeout=10
                )
        # 重置本地状态
        st.session_state.entered_room = False
        st.session_state.my_role = None
        st.success("已退出房间")
        st.rerun()

# 进入房间按钮
if not st.session_state.entered_room:
    if st.button("📥 进入房间", use_container_width=True, type="primary"):
        room_data = enter_room(room_id)
        if room_data:
            st.session_state.entered_room = True
            st.session_state.object_id = room_data["objectId"]
            st.session_state.board = room_data["board"]
            st.session_state.current_player = room_data["current_player"]
            st.session_state.players = room_data["players"]
            st.session_state.my_role = room_data["players"][get_device_id()]
            st.success(f"进入房间成功！你的角色：{st.session_state.my_role}")
            st.rerun()
        else:
            st.error("房间已满（2人），请稍后再试")

# 已进入房间：显示棋盘和状态
if st.session_state.entered_room and st.session_state.my_role:
    st.divider()
    st.info(f"""
    房间 {room_id}（{len(st.session_state.players)}/2人）
    你的角色：{st.session_state.my_role} | 当前回合：{st.session_state.current_player}
    {">>> 请等待对方落子..." if st.session_state.my_role != st.session_state.current_player else ">>> 轮到你落子！"}
    """)

    # 调试信息（帮助确认玩家列表）
    st.markdown(f"""
    <div class="debug-info">
    调试：当前玩家列表（设备ID）：{list(st.session_state.players.keys())}
    </div>
    """, unsafe_allow_html=True)

    if st.session_state.game_over:
        if st.session_state.winner == "平局":
            st.success("🟰 游戏结束：平局！")
        else:
            st.success(f"🏆 游戏结束：{st.session_state.winner} 获胜！")

    # 棋盘渲染
    st.subheader("游戏棋盘")
    with st.container():
        st.markdown('<div class="board-container">', unsafe_allow_html=True)
        rows = [st.columns(3, gap="small") for _ in range(3)]
        grid = [col for row in rows for col in row]

        for i in range(9):
            with grid[i]:
                cell_value = st.session_state.board[i]
                display_text = cell_value if cell_value else " "
                is_disabled = (
                        st.session_state.game_over
                        or (cell_value != "")
                        or (st.session_state.my_role != st.session_state.current_player)
                )

                if st.button(
                        label=display_text,
                        key=f"cell_{i}",
                        disabled=is_disabled,
                        use_container_width=True,
                        type="primary" if cell_value == "X" else "secondary"
                ):
                    st.session_state.board[i] = st.session_state.my_role
                    winner = check_winner(st.session_state.board)
                    if winner:
                        st.session_state.game_over = True
                        st.session_state.winner = winner
                        st.session_state.current_player = None
                    else:
                        st.session_state.current_player = "O" if st.session_state.current_player == "X" else "X"

                    try:
                        update_data = {
                            "board": st.session_state.board,
                            "current_player": st.session_state.current_player,
                            "game_over": st.session_state.game_over,
                            "winner": st.session_state.winner,
                            "players": st.session_state.players  # 同步玩家列表（防止丢失）
                        }
                        requests.put(
                            f"{BASE_API_URL}/{st.session_state.object_id}",
                            headers=HEADERS,
                            json=update_data,
                            timeout=10
                        )
                        st.success("落子成功！对方刷新后可见")
                    except Exception as e:
                        st.warning(f"同步失败：{str(e)}")
                    st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)

    if st.button("🔄 重新开始本局", use_container_width=True):
        st.session_state.board = ["", "", "", "", "", "", "", "", ""]
        st.session_state.current_player = "X"
        st.session_state.game_over = False
        st.session_state.winner = None
        try:
            requests.put(
                f"{BASE_API_URL}/{st.session_state.object_id}",
                headers=HEADERS,
                json={
                    "board": st.session_state.board,
                    "current_player": "X",
                    "game_over": False,
                    "winner": None,
                    "players": st.session_state.players  # 保留玩家列表
                },
                timeout=10
            )
            st.success("已重置游戏")
        except Exception as e:
            st.warning(f"重置失败：{str(e)}")
        st.rerun()

st.caption("""
💡 联机说明：
1. 第一位玩家进入自动成为X，第二位成为O
2. 若提示"已离开房间"，请确认是否被其他玩家移除
3. 调试信息显示当前房间内的设备ID，用于确认是否成功加入
""")