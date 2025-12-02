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
    # 设备ID在同一浏览器会话中永久保留（刷新不丢失）
    if "device_id" not in st.session_state:
        st.session_state.device_id = str(uuid.uuid4())
    return st.session_state.device_id

# ---------------------- 房间管理 ----------------------
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
    device_id = get_device_id()
    init_data = {
        "room_id": room_id,
        "board": ["", "", "", "", "", "", "", "", ""],
        "current_player": "X",
        "game_over": False,
        "winner": None,
        "player_count": 1,
        "players": {device_id: "X"}
    }
    res = requests.post(BASE_API_URL, headers=HEADERS, json=init_data, timeout=10)
    res.raise_for_status()
    init_data["objectId"] = res.json()["objectId"]
    return init_data

def enter_room(room_id):
    device_id = get_device_id()
    room_data = load_room(room_id)
    if not room_data:
        return create_room(room_id)
    if device_id in room_data.get("players", {}):
        return room_data
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
    return None

# ---------------------- 自动恢复状态（核心修复） ----------------------
def auto_restore_state(room_id):
    """页面刷新后自动恢复房间状态（无需手动点击刷新）"""
    if st.session_state.entered_room:
        # 尝试从云端加载最新数据
        room_data = load_room(room_id)
        if room_data:
            # 验证当前设备是否仍在房间中
            device_id = get_device_id()
            if device_id in room_data.get("players", {}):
                # 恢复状态
                st.session_state.object_id = room_data["objectId"]
                st.session_state.board = room_data.get("board", ["", "", "", "", "", "", "", "", ""])
                st.session_state.current_player = room_data.get("current_player", "X")
                st.session_state.game_over = room_data.get("game_over", False)
                st.session_state.winner = room_data.get("winner")
                st.session_state.players = room_data.get("players", {})
                st.session_state.my_role = room_data["players"][device_id]
                return True
            else:
                # 设备已不在房间中，重置状态
                st.session_state.entered_room = False
                st.session_state.my_role = None
                st.warning("你已被移出房间，请重新进入")
        else:
            # 房间已解散，重置状态
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

# 初始化会话状态（确保刷新后状态不丢失）
required_states = {
    "entered_room": False,
    "my_role": None,
    "object_id": None,
    "board": ["", "", "", "", "", "", "", "", ""],
    "current_player": "X",
    "game_over": False,
    "winner": None,
    "player_count": 0,
    "players": {}
}
for key, default in required_states.items():
    if key not in st.session_state:
        st.session_state[key] = default

# 页面加载时自动恢复状态（解决刷新后界面丢失）
auto_restore_state(room_id)

# 紧急清理按钮
if st.button("⚠️ 强制清理房间", use_container_width=True, type="secondary"):
    force_clean_room(room_id)
    st.rerun()

# 操作按钮：刷新/退出
col_refresh, col_exit = st.columns(2)
with col_refresh:
    if st.button("🔄 手动刷新", use_container_width=True):
        auto_restore_state(room_id)  # 复用自动恢复逻辑
        st.success("手动刷新完成")

with col_exit:
    if st.button("🚪 退出房间", use_container_width=True) and st.session_state.entered_room:
        room_data = load_room(room_id)
        if room_data:
            device_id = get_device_id()
            players = room_data.get("players", {}).copy()
            if device_id in players:
                del players[device_id]
                new_count = max(0, room_data.get("player_count", 0) - 1)
                if new_count == 0:
                    force_clean_room(room_id)
                else:
                    updated_data = {** room_data, "players": players, "player_count": new_count}
                    requests.put(f"{BASE_API_URL}/{room_data['objectId']}", headers=HEADERS, json=updated_data, timeout=10)
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
            st.error("房间已满，请先清理房间再进入")

# 已进入房间：显示棋盘（确保刷新后不丢失）
if st.session_state.entered_room and st.session_state.my_role:
    st.divider()
    st.info(f"""
    房间 {room_id}（{len(st.session_state.players)}/2人）
    你的角色：{st.session_state.my_role} | 当前回合：{st.session_state.current_player}
    {">>> 请等待对方落子..." if st.session_state.my_role != st.session_state.current_player else ">>> 轮到你落子！"}
    """)

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
                            "winner": st.session_state.winner
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
                    "winner": None
                },
                timeout=10
            )
            st.success("已重置游戏")
        except Exception as e:
            st.warning(f"重置失败：{str(e)}")
        st.rerun()

st.caption("""
💡 注意：刷新页面后会自动恢复房间状态，无需重新进入
""")