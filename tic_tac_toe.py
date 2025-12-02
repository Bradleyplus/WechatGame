import streamlit as st
import requests
import uuid

# ---------------------- 页面样式优化 ----------------------
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
        white-space: nowrap !important;
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
    .stColumns {
        flex-wrap: nowrap !important;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------- LeanCloud配置 ----------------------
APP_ID = "hiwS1jgaGdLqJhk2UtEwHGdK-gzGzoHsz"
APP_KEY = "bENg8Yr0UlGdt7NJB70i2VOW"
BASE_API_URL = "https://api.leancloud.cn/1.1/classes/GameState"
HEADERS = {
    "X-LC-Id": APP_ID,
    "X-LC-Key": APP_KEY,
    "Content-Type": "application/json"
}


# ---------------------- 胜负判断函数 ----------------------
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


# ---------------------- 读取房间状态 ----------------------
def load_game_state(room_id):
    try:
        params = {"where": f'{{"room_id":"{room_id}"}}', "limit": 1}
        response = requests.get(BASE_API_URL, headers=HEADERS, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data.get("results"):
            game_data = data["results"][0]
            return {
                "object_id": game_data["objectId"],
                "board": game_data.get("board", ["", "", "", "", "", "", "", "", ""]),
                "current_player": game_data.get("current_player", "X"),
                "game_over": game_data.get("game_over", False),
                "winner": game_data.get("winner"),
                "room_id": room_id,
                "player_count": game_data.get("player_count", 0),
                "players": game_data.get("players", {})
            }
        else:
            return None  # 房间不存在时返回None（区别于初始化）
    except requests.exceptions.RequestException as e:
        st.error(f"服务器连接失败：{str(e)}")
        return None


# ---------------------- 保存/删除房间状态 ----------------------
def save_game_state(state):
    if state["object_id"] == "local":
        st.warning("本地模式：仅本机可见操作")
        return
    try:
        valid_fields = {
            "room_id": str(state.get("room_id", "")),
            "board": state.get("board", ["", "", "", "", "", "", "", "", ""]) if isinstance(state.get("board"),
                                                                                            list) else ["", "", "", "",
                                                                                                        "", "", "", "",
                                                                                                        ""],
            "current_player": str(state.get("current_player", "X")),
            "game_over": bool(state.get("game_over", False)),
            "winner": state.get("winner") if state.get("winner") in ("X", "O", "平局", None) else None,
            "player_count": max(0, min(2, int(state.get("player_count", 0)))),
            "players": state.get("players", {})
        }
        update_url = f"{BASE_API_URL}/{state['object_id']}"
        response = requests.put(update_url, headers=HEADERS, json=valid_fields, timeout=10)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        st.warning(f"同步失败：{str(e)}")


def delete_room_state(object_id):
    """删除房间数据（当最后一个玩家退出时）"""
    try:
        delete_url = f"{BASE_API_URL}/{object_id}"
        response = requests.delete(delete_url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        st.success("房间已清空，可重新进入")
    except requests.exceptions.RequestException as e:
        st.warning(f"清除房间记录失败：{str(e)}")


# ---------------------- 房间管理（核心：退出时清除记录） ----------------------
def get_device_id():
    if "device_id" not in st.session_state:
        st.session_state.device_id = str(uuid.uuid4())
    return st.session_state.device_id


def enter_room(room_id):
    """进入房间：不存在则创建，存在则加入"""
    device_id = get_device_id()
    game_state = load_game_state(room_id)

    # 房间不存在，创建新房间
    if not game_state:
        init_game = {
            "room_id": room_id,
            "board": ["", "", "", "", "", "", "", "", ""],
            "current_player": "X",
            "game_over": False,
            "winner": None,
            "player_count": 1,
            "players": {device_id: "X"}  # 第一个玩家为X
        }
        create_response = requests.post(BASE_API_URL, headers=HEADERS, json=init_game, timeout=10)
        create_response.raise_for_status()
        new_game = create_response.json()
        return {
            **init_game,
            "object_id": new_game["objectId"]
        }

    # 房间存在，加入（最多2人）
    if game_state["player_count"] < 2 and device_id not in game_state["players"]:
        players = game_state["players"].copy()
        players[device_id] = "O"  # 第二个玩家为O
        return {
            **game_state,
            "player_count": game_state["player_count"] + 1,
            "players": players
        }
    return game_state  # 房间已满或已在房间中


def exit_room(room_id):
    """退出房间：最后一人退出时删除房间记录"""
    device_id = get_device_id()
    game_state = load_game_state(room_id)
    if not game_state:
        return None  # 房间不存在

    # 移除当前玩家
    players = game_state["players"].copy()
    if device_id in players:
        del players[device_id]
        new_count = max(0, game_state["player_count"] - 1)
    else:
        new_count = game_state["player_count"]

    # 最后一个玩家退出：删除房间记录
    if new_count == 0:
        delete_room_state(game_state["object_id"])
        return None  # 房间已删除

    # 还有玩家：更新状态（保留棋盘）
    return {
        **game_state,
        "player_count": new_count,
        "players": players
    }


# ---------------------- 页面初始化 ----------------------
st.title("🎮 双人井字棋（联机版）")

room_id = st.selectbox(
    "🔑 选择游戏房间",
    options=["8888", "6666"],
    index=0,
    key="room_selector"
)

# 初始化会话状态
if "entered_room" not in st.session_state:
    st.session_state.entered_room = False
if "device_id" not in st.session_state:
    st.session_state.device_id = str(uuid.uuid4())
if "my_role" not in st.session_state:
    st.session_state.my_role = None
if "object_id" not in st.session_state:
    st.session_state.object_id = ""

# 操作按钮
col_refresh, col_exit = st.columns(2)
with col_refresh:
    refresh_clicked = st.button("🔄 刷新状态", use_container_width=True)
with col_exit:
    exit_clicked = st.button("🚪 退出房间", use_container_width=True)

# 处理退出房间（核心：清除记录）
if exit_clicked and st.session_state.entered_room:
    exit_result = exit_room(room_id)
    # 重置本地状态
    st.session_state.entered_room = False
    st.session_state.my_role = None
    st.session_state.object_id = ""
    st.session_state.board = []
    st.success("已退出房间，房间记录已清除")
    st.rerun()

# 进入房间按钮
if not st.session_state.entered_room:
    if st.button("📥 进入房间", use_container_width=True):
        entered_state = enter_room(room_id)
        if entered_state:
            save_game_state(entered_state)
            st.session_state.entered_room = True
            st.session_state.object_id = entered_state["object_id"]
            st.session_state.board = entered_state["board"]
            st.session_state.current_player = entered_state["current_player"]
            st.session_state.game_over = entered_state["game_over"]
            st.session_state.winner = entered_state["winner"]
            st.session_state.player_count = entered_state["player_count"]
            st.session_state.players = entered_state["players"]
            st.session_state.my_role = entered_state["players"][st.session_state.device_id]
            st.success(f"已进入房间 {room_id}，您的角色：{st.session_state.my_role}")
            st.rerun()
        else:
            st.error("房间已满或创建失败")

# 已进入房间逻辑
if st.session_state.entered_room:
    if refresh_clicked:
        game_state = load_game_state(room_id)
        if not game_state:  # 房间已被删除（对方已退出）
            st.session_state.entered_room = False
            st.session_state.my_role = None
            st.error("房间已解散，请重新进入")
            st.rerun()
        st.session_state.board = game_state["board"]
        st.session_state.current_player = game_state["current_player"]
        st.session_state.game_over = game_state["game_over"]
        st.session_state.winner = game_state["winner"]
        st.session_state.player_count = game_state["player_count"]
        st.session_state.players = game_state["players"]
        st.session_state.my_role = game_state["players"].get(st.session_state.device_id)
        st.success("状态已刷新")

    # 显示状态
    st.divider()
    st.info(f"""
    📌 房间 {room_id}（{st.session_state.player_count}/2人）
    您的角色：{st.session_state.my_role} | 当前回合：{st.session_state.current_player}
    """)

    if st.session_state.game_over:
        if st.session_state.winner == "平局":
            st.success("🟰 游戏结束：平局！")
        else:
            st.success(f"🏆 游戏结束：玩家 {st.session_state.winner} 获胜！")

    # 九宫格棋盘
    st.subheader("游戏棋盘")
    with st.container():
        st.markdown('<div class="board-container">', unsafe_allow_html=True)

        row1 = st.columns(3, gap="small")
        row2 = st.columns(3, gap="small")
        row3 = st.columns(3, gap="small")
        grid_cols = [row1[0], row1[1], row1[2], row2[0], row2[1], row2[2], row3[0], row3[1], row3[2]]

        for grid_idx in range(9):
            with grid_cols[grid_idx]:
                btn_text = st.session_state.board[grid_idx] if st.session_state.board[grid_idx] != "" else " "
                is_disabled = (
                        st.session_state.game_over
                        or st.session_state.board[grid_idx] != ""
                        or st.session_state.my_role != st.session_state.current_player
                )

                if st.button(
                        btn_text,
                        key=f"btn_{room_id}_{grid_idx}",
                        disabled=is_disabled,
                        use_container_width=True,
                        type="primary" if st.session_state.board[grid_idx] == "X" else "secondary"
                ):
                    st.session_state.board[grid_idx] = st.session_state.my_role
                    st.session_state.winner = check_winner(st.session_state.board)
                    if st.session_state.winner is not None:
                        st.session_state.game_over = True
                        st.session_state.current_player = None
                    else:
                        st.session_state.current_player = "O" if st.session_state.current_player == "X" else "X"

                    save_game_state({
                        "object_id": st.session_state.object_id,
                        "room_id": room_id,
                        "board": st.session_state.board,
                        "current_player": st.session_state.current_player,
                        "game_over": st.session_state.game_over,
                        "winner": st.session_state.winner,
                        "player_count": st.session_state.player_count,
                        "players": st.session_state.players
                    })
                    st.success("落子成功！请对方刷新状态")
                    st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)

    # 重置游戏
    if st.button("🔄 重新开始本局", use_container_width=True):
        reset_board = ["", "", "", "", "", "", "", "", ""]
        st.session_state.board = reset_board
        st.session_state.current_player = "X"
        st.session_state.game_over = False
        st.session_state.winner = None
        save_game_state({
            "object_id": st.session_state.object_id,
            "room_id": room_id,
            "board": reset_board,
            "current_player": "X",
            "game_over": False,
            "winner": None,
            "player_count": st.session_state.player_count,
            "players": st.session_state.players
        })
        st.rerun()

st.caption("""
💡 操作指南：
1. 选择房间→点击「进入房间」（自动分配X/O角色）
2. 只能在自己的回合落子，已落子格子不可修改
3. 最后一人退出房间时，自动清除房间记录，避免占用
""")