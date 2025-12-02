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
    @media (max-width: 400px) {
        .board-container {
            max-width: 180px !important;
        }
        .stButton > button {
            height: 50px !important;
            font-size: 1.2rem !important;
        }
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
    """判断胜负"""
    win_combinations = [
        [0, 1, 2], [3, 4, 5], [6, 7, 8],  # 横
        [0, 3, 6], [1, 4, 7], [2, 5, 8],  # 竖
        [0, 4, 8], [2, 4, 6]  # 斜
    ]
    for combo in win_combinations:
        a, b, c = combo
        if board[a] == board[b] == board[c] != "":
            return board[a]
    if "" not in board:
        return "平局"
    return None


def get_device_id():
    """获取设备唯一ID（确保角色固定）"""
    if "device_id" not in st.session_state:
        st.session_state.device_id = str(uuid.uuid4())
    return st.session_state.device_id


# ---------------------- 房间管理 ----------------------
def force_clean_room(room_id):
    """强制清理房间记录"""
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
    """加载房间状态"""
    try:
        params = {"where": f'{{"room_id":"{room_id}"}}', "limit": 1}
        res = requests.get(BASE_API_URL, headers=HEADERS, params=params, timeout=10)
        res.raise_for_status()
        data = res.json()
        return data["results"][0] if data.get("results") else None
    except Exception as e:
        st.error(f"加载房间失败：{str(e)}")
        return None


def create_room(room_id):
    """创建新房间（第一个玩家为X）"""
    device_id = get_device_id()
    init_data = {
        "room_id": room_id,
        "board": ["", "", "", "", "", "", "", "", ""],  # 初始空棋盘
        "current_player": "X",  # 初始回合为X
        "game_over": False,
        "winner": None,
        "player_count": 1,
        "players": {device_id: "X"}  # 绑定设备与角色
    }
    res = requests.post(BASE_API_URL, headers=HEADERS, json=init_data, timeout=10)
    res.raise_for_status()
    init_data["objectId"] = res.json()["objectId"]
    return init_data


def enter_room(room_id):
    """进入房间（分配角色）"""
    device_id = get_device_id()
    room_data = load_room(room_id)

    # 房间不存在，创建新房间
    if not room_data:
        return create_room(room_id)

    # 已在房间中，直接返回
    if device_id in room_data.get("players", {}):
        return room_data

    # 房间未满（<2人），分配为O
    if room_data.get("player_count", 0) < 2:
        updated_players = room_data["players"].copy()
        updated_players[device_id] = "O"
        updated_data = {
            **room_data,
            "player_count": room_data["player_count"] + 1,
            "players": updated_players
        }
        requests.put(f"{BASE_API_URL}/{room_data['objectId']}", headers=HEADERS, json=updated_data, timeout=10)
        return updated_data

    # 房间已满
    return None


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
    "board": ["", "", "", "", "", "", "", "", ""],  # 强制初始化为空棋盘
    "current_player": "X",
    "game_over": False,
    "winner": None,
    "player_count": 0,
    "players": {}
}
for key, default in required_states.items():
    if key not in st.session_state:
        st.session_state[key] = default

# 紧急清理按钮
if st.button("⚠️ 强制清理房间", use_container_width=True, type="secondary"):
    force_clean_room(room_id)
    st.rerun()

# 操作按钮：刷新/退出
col_refresh, col_exit = st.columns(2)
with col_refresh:
    if st.button("🔄 刷新状态", use_container_width=True):
        if st.session_state.entered_room:
            room_data = load_room(room_id)
            if not room_data:
                st.session_state.entered_room = False
                st.error("房间已解散，请重新进入")
            else:
                # 强制同步云端数据到本地
                st.session_state.board = room_data.get("board", ["", "", "", "", "", "", "", "", ""])
                st.session_state.current_player = room_data.get("current_player", "X")
                st.session_state.game_over = room_data.get("game_over", False)
                st.session_state.winner = room_data.get("winner")
                st.session_state.players = room_data.get("players", {})
                st.session_state.my_role = st.session_state.players.get(get_device_id())
                st.success("状态已同步")
        else:
            st.info("请先进入房间")

with col_exit:
    if st.button("🚪 退出房间", use_container_width=True) and st.session_state.entered_room:
        # 退出时更新房间状态
        room_data = load_room(room_id)
        if room_data:
            device_id = get_device_id()
            players = room_data.get("players", {}).copy()
            if device_id in players:
                del players[device_id]
                new_count = max(0, room_data.get("player_count", 0) - 1)
                # 最后一人退出则删除房间
                if new_count == 0:
                    force_clean_room(room_id)
                else:
                    updated_data = {**room_data, "players": players, "player_count": new_count}
                    requests.put(f"{BASE_API_URL}/{room_data['objectId']}", headers=HEADERS, json=updated_data,
                                 timeout=10)
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
            # 初始化本地状态（关键：确保角色和回合正确）
            st.session_state.entered_room = True
            st.session_state.object_id = room_data["objectId"]
            st.session_state.board = room_data["board"]
            st.session_state.current_player = room_data["current_player"]
            st.session_state.players = room_data["players"]
            st.session_state.my_role = room_data["players"][get_device_id()]  # 强制获取自己的角色
            st.success(f"进入房间成功！你的角色：{st.session_state.my_role}（当前回合：{st.session_state.current_player}）")
            st.rerun()
        else:
            st.error("房间已满，请先清理房间再进入")

# 已进入房间：显示棋盘和落子逻辑
if st.session_state.entered_room and st.session_state.my_role:
    st.divider()
    st.info(f"""
    房间 {room_id}（{st.session_state.players.__len__()}/2人）
    你的角色：{st.session_state.my_role} | 当前回合：{st.session_state.current_player}
    {">>> 请等待对方落子..." if st.session_state.my_role != st.session_state.current_player else ">>> 轮到你落子！"}
    """)

    # 游戏结束提示
    if st.session_state.game_over:
        if st.session_state.winner == "平局":
            st.success("🟰 游戏结束：平局！")
        else:
            st.success(f"🏆 游戏结束：{st.session_state.winner} 获胜！")

    # 棋盘渲染（核心修复：落子按钮启用/禁用逻辑）
    st.subheader("游戏棋盘")
    with st.container():
        st.markdown('<div class="board-container">', unsafe_allow_html=True)
        rows = [st.columns(3, gap="small") for _ in range(3)]  # 3行3列
        grid = [col for row in rows for col in row]  # 扁平化为9个格子

        for i in range(9):  # 遍历9个格子
            with grid[i]:
                # 格子当前值（空字符串表示未落子）
                cell_value = st.session_state.board[i]
                display_text = cell_value if cell_value else " "  # 空格子显示空格

                # 关键修复：按钮禁用条件（严格判断）
                # 禁用场景：1.游戏结束 2.已有棋子 3.不是自己的回合
                is_disabled = (
                        st.session_state.game_over
                        or (cell_value != "")  # 已有棋子（用空字符串判断，避免空格误判）
                        or (st.session_state.my_role != st.session_state.current_player)  # 不是自己回合
                )

                # 落子按钮（修复参数类型，确保可点击）
                if st.button(
                        label=display_text,
                        key=f"cell_{i}",
                        disabled=is_disabled,
                        use_container_width=True,
                        type="primary" if cell_value == "X" else "secondary"
                ):
                    # 执行落子
                    st.session_state.board[i] = st.session_state.my_role  # 用自己的角色落子

                    # 判断胜负
                    winner = check_winner(st.session_state.board)
                    if winner:
                        st.session_state.game_over = True
                        st.session_state.winner = winner
                        st.session_state.current_player = None  # 游戏结束无当前回合
                    else:
                        # 切换回合（X→O，O→X）
                        st.session_state.current_player = "O" if st.session_state.current_player == "X" else "X"

                    # 同步到云端
                    try:
                        update_data = {
                            "board": st.session_state.board,
                            "current_player": st.session_state.current_player,
                            "game_over": st.session_state.game_over,
                            "winner": st.session_state.winner
                        }
                        requests.put(
                            f"{BASE_API_URL}/{st.session_state.object_id}",
                            headers=HEADERS,
                            json=update_data,
                            timeout=10
                        )
                        st.success("落子成功！请对方刷新查看")
                    except Exception as e:
                        st.warning(f"同步失败：{str(e)}")

                    # 刷新页面生效
                    st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)

    # 重新开始按钮
    if st.button("🔄 重新开始本局", use_container_width=True):
        st.session_state.board = ["", "", "", "", "", "", "", "", ""]
        st.session_state.current_player = "X"
        st.session_state.game_over = False
        st.session_state.winner = None
        # 同步到云端
        try:
            requests.put(
                f"{BASE_API_URL}/{st.session_state.object_id}",
                headers=HEADERS,
                json={
                    "board": st.session_state.board,
                    "current_player": "X",
                    "game_over": False,
                    "winner": None
                },
                timeout=10
            )
            st.success("已重置游戏")
        except Exception as e:
            st.warning(f"重置失败：{str(e)}")
        st.rerun()

# 操作指南
st.caption("""
💡 落子说明：
1. 进入房间后，等待显示"轮到你落子"
2. 点击空白格子即可落下你的棋子（X或O）
3. 落子后需等待对方刷新页面
4. 只能在自己的回合落子，已落子的格子不能重复点击
""")