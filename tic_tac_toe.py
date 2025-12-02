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
        return "Draw"
    return None


def get_device_id():
    if "device_id" not in st.session_state:
        st.session_state.device_id = str(uuid.uuid4())
    return st.session_state.device_id


# ---------------------- 房间管理（核心优化：强制房间号唯一） ----------------------
def force_clean_room(room_id):
    """清理指定房间号的所有记录（确保唯一）"""
    try:
        # 查询该房间号的所有记录
        params = {"where": f'{{"room_id":"{room_id}"}}'}
        res = requests.get(BASE_API_URL, headers=HEADERS, params=params, timeout=10)
        if res.status_code == 200 and res.json().get("results"):
            # 逐个删除所有记录（防止重复）
            for record in res.json()["results"]:
                object_id = record["objectId"]
                requests.delete(f"{BASE_API_URL}/{object_id}", headers=HEADERS, timeout=10)
            st.success(f"All records for room {room_id} cleaned!")
            time.sleep(1)
            return True
        else:
            st.info(f"No records for room {room_id}")
    except Exception as e:
        st.error(f"Clean error: {str(e)}")
    return False


def load_room(room_id, debug=False):
    """加载房间号对应的唯一房间（只取最新的有效记录）"""
    try:
        # 严格查询指定房间号的记录，按创建时间倒序（确保取最新的）
        params = {
            "where": f'{{"room_id":"{room_id}"}}',
            "limit": 1,
            "order": "-createdAt"  # 最新创建的优先
        }
        res = requests.get(BASE_API_URL, headers=HEADERS, params=params, timeout=10)
        res.raise_for_status()
        data = res.json()
        if data.get("results"):
            room_data = data["results"][0]
            room_data["players"] = room_data.get("players", {})
            if debug:
                st.write(f"Loaded room (ID: {room_data['objectId']}): {room_data}")
            return room_data
        if debug:
            st.write(f"No room found for {room_id}")
        return None
    except Exception as e:
        st.error(f"Load room error: {str(e)}")
        return None


def create_room(room_id):
    """创建房间前先检查是否已存在，确保唯一"""
    # 先检查是否已有该房间号的记录（防止重复创建）
    existing_room = load_room(room_id)
    if existing_room:
        st.warning(f"Room {room_id} already exists! Joining existing room...")
        return existing_room

    # 确认不存在后再创建
    device_id = get_device_id()
    init_data = {
        "room_id": room_id,
        "board": ["", "", "", "", "", "", "", "", ""],
        "current_player": "X",
        "game_over": False,
        "winner": None,
        "players": {device_id: "X"}
    }
    try:
        res = requests.post(BASE_API_URL, headers=HEADERS, json=init_data, timeout=10)
        res.raise_for_status()
        new_data = res.json()
        init_data["objectId"] = new_data["objectId"]
        st.success(f"Room {room_id} created (Unique ID: {new_data['objectId'][:8]})")
        return init_data
    except Exception as e:
        st.error(f"Create room failed: {str(e)}")
        return None


def enter_room(room_id):
    """进入房间时强制绑定到同一房间号的唯一记录"""
    device_id = get_device_id()
    room_data = load_room(room_id)

    # 情况1：房间不存在，创建新房间（已确保唯一）
    if not room_data:
        return create_room(room_id)

    # 情况2：已在房间中，直接返回
    if device_id in room_data["players"]:
        st.info(f"Already in room {room_id} (role: {room_data['players'][device_id]})")
        return room_data

    # 情况3：房间未满，加入（强制同步并验证）
    if len(room_data["players"]) < 2:
        updated_players = room_data["players"].copy()
        updated_players[device_id] = "O"
        updated_data = {**room_data, "players": updated_players}

        try:
            # 同步到云端
            put_res = requests.put(
                f"{BASE_API_URL}/{room_data['objectId']}",
                headers=HEADERS,
                json=updated_data,
                timeout=10
            )
            put_res.raise_for_status()

            # 强制等待并验证是否加入成功
            time.sleep(1.5)  # 给云端足够同步时间
            verified_room = load_room(room_id)
            if verified_room and device_id in verified_room["players"]:
                st.success(f"Joined room {room_id} as O (Unique ID: {verified_room['objectId'][:8]})")
                return verified_room
            else:
                st.error("Failed to join: Server did not save your info")
                return None

        except Exception as e:
            st.error(f"Join error: {str(e)}")
            return None

    # 情况4：房间已满
    st.error(f"Room {room_id} is full (2 players). Clean room first.")
    return None


# ---------------------- 状态恢复 ----------------------
def auto_restore_state(room_id):
    if st.session_state.entered_room:
        room_data = load_room(room_id)
        if not room_data:
            st.warning(f"Room {room_id} not found. Please re-enter.")
            st.session_state.entered_room = False
            return False
        else:
            device_id = get_device_id()
            if device_id in room_data["players"]:
                # 恢复状态时绑定到同一房间唯一ID
                st.session_state.object_id = room_data["objectId"]
                st.session_state.board = room_data.get("board", ["", "", "", "", "", "", "", "", ""])
                st.session_state.current_player = room_data.get("current_player", "X")
                st.session_state.game_over = room_data.get("game_over", False)
                st.session_state.winner = room_data.get("winner")
                st.session_state.players = room_data["players"]
                st.session_state.my_role = room_data["players"][device_id]
                return True
            else:
                st.session_state.entered_room = False
                st.warning(f"You are not in room {room_id}. Please re-enter.")
    return False


# ---------------------- 主页面逻辑 ----------------------
st.title("🎮 Two-Player Tic-Tac-Toe (Online)")

# 房间选择（强调唯一房间号）
room_id = st.selectbox(
    "🔑 Select Game Room (Unique)",
    options=["8888", "6666"],
    index=0,
    key="room_selector"
)

# 初始化会话状态
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

# 显示关键调试信息（用于确认是否同房间）
device_id = get_device_id()
st.markdown(f"""
<div class="debug-box">
- Your device ID: <strong>{device_id[:8]}...</strong><br>
- Room number: <strong>{room_id}</strong><br>
{'- Room unique ID: <span class="room-id-box">{st.session_state.object_id[:8]}...</span>' if st.session_state.object_id else ''}
</div>
""", unsafe_allow_html=True)

# 自动恢复状态
auto_restore_state(room_id)

# 强制清理按钮（确保清理该房间号的所有记录）
if st.button("⚠️ Force Clean Room", use_container_width=True, type="secondary"):
    if force_clean_room(room_id):
        st.rerun()

# 操作按钮：刷新/退出
col_refresh, col_exit = st.columns(2)
with col_refresh:
    if st.button("🔄 Manual Refresh", use_container_width=True):
        auto_restore_state(room_id)
        st.success("Manual refresh completed")

with col_exit:
    if st.button("🚪 Exit Room", use_container_width=True) and st.session_state.entered_room:
        room_data = load_room(room_id)
        if room_data:
            device_id = get_device_id()
            players = room_data["players"].copy()
            if device_id in players:
                del players[device_id]
                updated_data = {**room_data, "players": players}
                try:
                    requests.put(
                        f"{BASE_API_URL}/{room_data['objectId']}",
                        headers=HEADERS,
                        json=updated_data,
                        timeout=10
                    )
                except Exception as e:
                    st.warning(f"Exit sync failed: {str(e)}")
        st.session_state.entered_room = False
        st.session_state.my_role = None
        st.success("Exited room")
        st.rerun()

# 进入房间按钮
if not st.session_state.entered_room:
    if st.button("📥 Enter Room", use_container_width=True, type="primary"):
        with st.spinner(f"Joining room {room_id}..."):
            room_data = enter_room(room_id)
            if room_data:
                st.session_state.entered_room = True
                st.session_state.object_id = room_data["objectId"]
                st.session_state.board = room_data.get("board", ["", "", "", "", "", "", "", "", ""])
                st.session_state.current_player = room_data.get("current_player", "X")
                st.session_state.players = room_data["players"]
                st.session_state.my_role = room_data["players"][device_id]
                st.rerun()

# 已进入房间：显示棋盘和房间唯一标识
if st.session_state.entered_room and st.session_state.my_role:
    st.divider()
    # 显示房间唯一ID（两人需一致才在同一房间）
    st.info(f"""
    Room {room_id} (Unique ID: {st.session_state.object_id[:8]})<br>
    Players: {len(st.session_state.players)}/2 | Your role: {st.session_state.my_role}<br>
    Current turn: {st.session_state.current_player}
    {">>> Waiting for opponent..." if st.session_state.my_role != st.session_state.current_player else ">>> Your turn!"}
    """)

    # 显示房间内所有玩家的设备ID（方便核对）
    st.markdown(f"""
    <div class="debug-box">
    Players in room:<br>
    {[f"- {k[:8]}...({v})" for k, v in st.session_state.players.items()]}
    </div>
    """, unsafe_allow_html=True)

    if st.session_state.game_over:
        if st.session_state.winner == "Draw":
            st.success("🟰 Game over: Draw!")
        else:
            st.success(f"🏆 Game over: {st.session_state.winner} wins!")

    # 棋盘渲染
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

                    try:
                        update_data = {
                            "board": st.session_state.board,
                            "current_player": st.session_state.current_player,
                            "game_over": st.session_state.game_over,
                            "winner": st.session_state.winner,
                            "players": st.session_state.players
                        }
                        requests.put(
                            f"{BASE_API_URL}/{st.session_state.object_id}",
                            headers=HEADERS,
                            json=update_data,
                            timeout=10
                        )
                        st.success("Move saved! Opponent can refresh.")
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
                    "winner": None,
                    "players": st.session_state.players
                },
                timeout=10
            )
            st.success("Game restarted")
        except Exception as e:
            st.warning(f"Restart failed: {str(e)}")
        st.rerun()

st.caption("""
💡 How to confirm same room?
- Both players must see the SAME "Room unique ID" (e.g., abc123...)
- If not, click "Force Clean Room" and re-enter
""")