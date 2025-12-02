import streamlit as st
import requests
import uuid
import time

# ---------------------- 页面配置与样式 ----------------------
st.set_page_config(
    page_title="Two-Player Tic-Tac-Toe",
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
    .debug-box {
        background-color: #f0f2f6;
        padding: 10px;
        border-radius: 5px;
        font-size: 0.8rem;
        margin: 10px 0;
    }
    .room-id-box {
        color: #2196F3;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------- 云存储配置（LeanCloud字段仅保留必要项） ----------------------
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
        return "Draw"
    return None


def get_device_id():
    if "device_id" not in st.session_state:
        st.session_state.device_id = str(uuid.uuid4())
    return st.session_state.device_id


# ---------------------- 房间管理（核心：仅传递LeanCloud定义的字段） ----------------------
def force_clean_room(room_id):
    """清理指定房间号的所有记录（避免冗余）"""
    try:
        params = {"where": f'{{"room_id":"{room_id}"}}'}
        res = requests.get(BASE_API_URL, headers=HEADERS, params=params, timeout=10)
        if res.status_code == 200 and res.json().get("results"):
            for record in res.json()["results"]:
                requests.delete(f"{BASE_API_URL}/{record['objectId']}", headers=HEADERS, timeout=10)
            st.success(f"Room {room_id} cleaned (all records deleted)")
            time.sleep(1)
            return True
        st.info(f"No records for room {room_id}")
    except Exception as e:
        st.error(f"Clean error: {str(e)}")
    return False


def load_room(room_id, debug=False):
    """加载房间（仅保留必要字段）"""
    try:
        params = {
            "where": f'{{"room_id":"{room_id}"}}',
            "limit": 1,
            "order": "-createdAt"
        }
        res = requests.get(BASE_API_URL, headers=HEADERS, params=params, timeout=10)
        res.raise_for_status()
        data = res.json()
        if data.get("results"):
            room_data = data["results"][0]
            # 确保players字段存在（LeanCloud返回可能缺失）
            room_data["players"] = room_data.get("players", {})
            if debug:
                st.write(f"Loaded room (ID: {room_data['objectId']}): {room_data}")
            return room_data
        if debug:
            st.write(f"No room found for {room_id}")
        return None
    except Exception as e:
        st.error(f"Load error: {str(e)}")
        return None


def create_room(room_id):
    """创建房间（仅传递LeanCloud定义的字段）"""
    existing_room = load_room(room_id)
    if existing_room:
        st.warning(f"Room {room_id} exists! Joining...")
        return existing_room

    device_id = get_device_id()
    # 仅包含LeanCloud中定义的字段（去掉冗余的player_count）
    init_data = {
        "room_id": room_id,
        "board": ["", "", "", "", "", "", "", "", ""],
        "current_player": "X",
        "game_over": False,
        "winner": None,
        "players": {device_id: "X"}  # 仅存储设备ID-角色映射
    }
    try:
        res = requests.post(BASE_API_URL, headers=HEADERS, json=init_data, timeout=10)
        res.raise_for_status()
        new_data = res.json()
        init_data["objectId"] = new_data["objectId"]
        st.success(f"Room {room_id} created (Unique ID: {new_data['objectId'][:8]})")
        return init_data
    except Exception as e:
        # 显示详细错误（方便排查）
        st.error(f"Create failed: {str(e)} | Response: {res.text if 'res' in locals() else 'No response'}")
        return None


def enter_room(room_id):
    """进入房间（更新请求仅传递必要字段）"""
    device_id = get_device_id()
    room_data = load_room(room_id)

    if not room_data:
        return create_room(room_id)

    if device_id in room_data["players"]:
        st.info(f"Already in room {room_id} (role: {room_data['players'][device_id]})")
        return room_data

    # 房间未满（players长度<2）
    if len(room_data["players"]) < 2:
        updated_players = room_data["players"].copy()
        updated_players[device_id] = "O"
        # 仅更新必要字段（去掉冗余的player_count）
        updated_data = {
            "players": updated_players,
            "current_player": room_data["current_player"],  # 保留原回合
            "board": room_data["board"]
        }
        try:
            put_url = f"{BASE_API_URL}/{room_data['objectId']}"
            res = requests.put(put_url, headers=HEADERS, json=updated_data, timeout=10)
            res.raise_for_status()

            time.sleep(1.5)
            verified_room = load_room(room_id)
            if verified_room and device_id in verified_room["players"]:
                st.success(f"Joined room {room_id} as O (Unique ID: {verified_room['objectId'][:8]})")
                return verified_room
            st.error("Join failed: Server did not save your role")
            return None
        except Exception as e:
            st.error(f"Join error: {str(e)} | Response: {res.text if 'res' in locals() else 'No response'}")
            return None

    st.error(f"Room {room_id} is full (2 players)")
    return None


# ---------------------- 状态恢复 ----------------------
def auto_restore_state(room_id):
    if st.session_state.entered_room:
        room_data = load_room(room_id)
        if not room_data:
            st.warning(f"Room {room_id} not found. Re-enter required.")
            st.session_state.entered_room = False
            return False
        device_id = get_device_id()
        if device_id in room_data["players"]:
            st.session_state.object_id = room_data["objectId"]
            st.session_state.board = room_data.get("board", ["", "", "", "", "", "", "", "", ""])
            st.session_state.current_player = room_data.get("current_player", "X")
            st.session_state.game_over = room_data.get("game_over", False)
            st.session_state.winner = room_data.get("winner")
            st.session_state.players = room_data["players"]
            st.session_state.my_role = room_data["players"][device_id]
            return True
        st.session_state.entered_room = False
        st.warning(f"You're not in room {room_id}. Re-enter.")
    return False


# ---------------------- 主页面逻辑 ----------------------
st.title("🎮 Two-Player Tic-Tac-Toe (Online)")

room_id = st.selectbox(
    "🔑 Select Game Room (Unique)",
    options=["8888", "6666"],
    index=0,
    key="room_selector"
)

# 初始化会话状态（去掉player_count）
required_states = {
    "entered_room": False,
    "my_role": None,
    "object_id": None,
    "board": ["", "", "", "", "", "", "", "", ""],
    "current_player": "X",
    "game_over": False,
    "winner": None,
    "players": {}
}
for key, default in required_states.items():
    if key not in st.session_state:
        st.session_state[key] = default

# 调试信息
device_id = get_device_id()
st.markdown(f"""
<div class="debug-box">
- Your device ID: <strong>{device_id[:8]}...</strong><br>
- Room number: <strong>{room_id}</strong><br>
{'- Room unique ID: <span class="room-id-box">{st.session_state.object_id[:8]}...</span>' if st.session_state.object_id else ''}
</div>
""", unsafe_allow_html=True)

auto_restore_state(room_id)

# 操作按钮
if st.button("⚠️ Force Clean Room", use_container_width=True, type="secondary"):
    if force_clean_room(room_id):
        st.rerun()

col_refresh, col_exit = st.columns(2)
with col_refresh:
    if st.button("🔄 Manual Refresh", use_container_width=True):
        auto_restore_state(room_id)
        st.success("Refreshed")

with col_exit:
    if st.button("🚪 Exit Room", use_container_width=True) and st.session_state.entered_room:
        room_data = load_room(room_id)
        if room_data:
            device_id = get_device_id()
            players = room_data["players"].copy()
            if device_id in players:
                del players[device_id]
                requests.put(
                    f"{BASE_API_URL}/{room_data['objectId']}",
                    headers=HEADERS,
                    json={"players": players},
                    timeout=10
                )
        st.session_state.entered_room = False
        st.success("Exited")
        st.rerun()

# 进入房间
if not st.session_state.entered_room:
    if st.button("📥 Enter Room", use_container_width=True, type="primary"):
        with st.spinner(f"Joining room {room_id}..."):
            room_data = enter_room(room_id)
            if room_data:
                st.session_state.entered_room = True
                st.session_state.object_id = room_data["objectId"]
                st.session_state.board = room_data["board"]
                st.session_state.current_player = room_data["current_player"]
                st.session_state.players = room_data["players"]
                st.session_state.my_role = room_data["players"][device_id]
                st.rerun()

# 游戏界面
if st.session_state.entered_room and st.session_state.my_role:
    st.divider()
    st.info(f"""
    Room {room_id} (Unique ID: {st.session_state.object_id[:8]})<br>
    Players: {len(st.session_state.players)}/2 | Your role: {st.session_state.my_role}<br>
    Current turn: {st.session_state.current_player}
    {">>> Waiting for opponent..." if st.session_state.my_role != st.session_state.current_player else ">>> Your turn!"}
    """)

    st.markdown(f"""
    <div class="debug-box">
    Players in room:<br>
    {[f"- {k[:8]}...({v})" for k, v in st.session_state.players.items()]}
    </div>
    """, unsafe_allow_html=True)

    if st.session_state.game_over:
        result = "Draw!" if st.session_state.winner == "Draw" else f"{st.session_state.winner} wins!"
        st.success(f"🏆 Game over: {result}")

    # 棋盘
    st.subheader("Game Board")
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

                    # 落子后同步（仅传递必要字段）
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
                        st.success("Move saved! Opponent refresh to see.")
                    except Exception as e:
                        st.warning(f"Sync failed: {str(e)}")
                    st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)

    if st.button("🔄 Restart Game", use_container_width=True):
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
            st.success("Game restarted")
        except Exception as e:
            st.warning(f"Restart failed: {str(e)}")
        st.rerun()

st.caption("""
💡 Fix for "400 Error":
1. Click "Force Clean Room" to delete old records
2. Re-enter room (ensure only necessary fields are sent to LeanCloud)
""")