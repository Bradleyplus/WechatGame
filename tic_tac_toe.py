import streamlit as st
import requests
import time

# ---------------------- 页面样式优化（纯原生组件，解决手机九宫格显示） ----------------------
st.set_page_config(
    page_title="双人井字棋",
    layout="centered",  # 居中布局适配手机
    initial_sidebar_state="collapsed"
)

# 自定义CSS：强制按钮正方形显示，适配手机屏幕（纯原生实现）
st.markdown("""
<style>
    /* 确保棋盘容器紧凑 */
    .board-container {
        width: 100%;
        max-width: 300px;
        margin: 0 auto;
    }
    /* 按钮样式：正方形、适配手机 */
    .stButton > button {
        width: 100% !important;
        height: 90px !important;
        font-size: 2rem !important;
        padding: 0 !important;
        margin: 2px !important;  # 格子间微小间距
    }
    /* 手机端适配 */
    @media (max-width: 400px) {
        .stButton > button {
            height: 80px !important;
            font-size: 1.5rem !important;
        }
    }
</style>
""", unsafe_allow_html=True)

# ---------------------- 1. LeanCloud配置 ----------------------
APP_ID = "hiwS1jgaGdLqJhk2UtEwHGdK-gzGzoHsz"
APP_KEY = "bENg8Yr0UlGdt7NJB70i2VOW"
BASE_API_URL = "https://api.leancloud.cn/1.1/classes/GameState"
HEADERS = {
    "X-LC-Id": APP_ID,
    "X-LC-Key": APP_KEY,
    "Content-Type": "application/json"
}


# ---------------------- 2. 胜负判断函数 ----------------------
def check_winner(board):
    win_combinations = [
        [0, 1, 2], [3, 4, 5], [6, 7, 8],  # 行
        [0, 3, 6], [1, 4, 7], [2, 5, 8],  # 列
        [0, 4, 8], [2, 4, 6]  # 对角线
    ]
    for combo in win_combinations:
        a, b, c = combo
        if board[a] == board[b] == board[c] != "":
            return board[a]
    if "" not in board:
        return "平局"
    return None


# ---------------------- 3. 读取房间状态（人数限制） ----------------------
def load_game_state(room_id):
    try:
        params = {"where": f'{{"room_id":"{room_id}"}}', "limit": 1}
        response = requests.get(BASE_API_URL, headers=HEADERS, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data.get("results"):
            game_data = data["results"][0]
            player_count = game_data.get("player_count", 0)
            return {
                "object_id": game_data["objectId"],
                "board": game_data["board"],
                "current_player": game_data["current_player"],
                "game_over": game_data["game_over"],
                "winner": game_data["winner"],
                "room_id": room_id,
                "player_count": player_count
            }
        else:
            init_game = {
                "room_id": room_id,
                "board": ["", "", "", "", "", "", "", "", ""],
                "current_player": "X",
                "game_over": False,
                "winner": None,
                "player_count": 0
            }
            create_response = requests.post(BASE_API_URL, headers=HEADERS, json=init_game, timeout=10)
            create_response.raise_for_status()
            new_game = create_response.json()
            return {
                "object_id": new_game["objectId"],
                "board": ["", "", "", "", "", "", "", "", ""],
                "current_player": "X",
                "game_over": False,
                "winner": None,
                "room_id": room_id,
                "player_count": 0
            }
    except requests.exceptions.RequestException as e:
        st.error(f"服务器连接失败：{str(e)}")
        return {
            "object_id": "local",
            "board": ["", "", "", "", "", "", "", "", ""],
            "current_player": "X",
            "game_over": False,
            "winner": None,
            "room_id": room_id,
            "player_count": 0
        }


# ---------------------- 4. 保存房间状态 ----------------------
def save_game_state(state):
    if state["object_id"] == "local":
        st.warning("本地模式：仅本机可见操作")
        return
    try:
        update_url = f"{BASE_API_URL}/{state['object_id']}"
        update_data = {
            "room_id": state["room_id"],
            "board": state["board"],
            "current_player": state["current_player"],
            "game_over": state["game_over"],
            "winner": state["winner"],
            "player_count": state["player_count"]
        }
        response = requests.put(update_url, headers=HEADERS, json=update_data, timeout=10)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        st.warning(f"同步失败：{str(e)}")


# ---------------------- 5. 房间人数管理 ----------------------
def enter_room(room_id, current_state):
    if current_state["player_count"] < 2:
        new_count = current_state["player_count"] + 1
        return {**current_state, "player_count": new_count}
    else:
        return current_state


# ---------------------- 6. 页面初始化 ----------------------
st.title("🎮 双人井字棋（联机版）")

# 固定房间选择
room_id = st.selectbox(
    "🔑 选择游戏房间",
    options=["8888", "6666"],
    index=0,
    key="room_selector"
)

# 拉取房间状态并处理玩家进入
game_state = load_game_state(room_id)
if "entered_room" not in st.session_state:
    game_state = enter_room(room_id, game_state)
    save_game_state(game_state)
    st.session_state.entered_room = True

# 更新本地状态
st.session_state.object_id = game_state["object_id"]
st.session_state.board = game_state["board"]
st.session_state.current_player = game_state["current_player"]
st.session_state.game_over = game_state["game_over"]
st.session_state.winner = game_state["winner"]
st.session_state.room_id = room_id
st.session_state.player_count = game_state["player_count"]

# ---------------------- 7. 房间状态提示 ----------------------
st.divider()
if st.session_state.player_count < 2:
    st.info(f"📌 房间 {room_id} - 等待玩家加入（当前{st.session_state.player_count}/2人）")
else:
    st.info(f"📌 房间 {room_id} - 已满（2/2人）| 当前回合：玩家 {st.session_state.current_player}")

if st.session_state.game_over:
    if st.session_state.winner == "平局":
        st.success(f"🟰 游戏结束：平局！")
    else:
        st.success(f"🏆 游戏结束：玩家 {st.session_state.winner} 获胜！")

# ---------------------- 8. 原生九宫格棋盘（核心修复，无外部依赖） ----------------------
st.subheader("游戏棋盘")
# 用原生columns创建3x3网格（适配手机）
with st.container():  # 容器确保棋盘紧凑
    st.markdown('<div class="board-container">', unsafe_allow_html=True)

    # 第一行
    col1, col2, col3 = st.columns(3, gap="small")
    # 第二行
    col4, col5, col6 = st.columns(3, gap="small")
    # 第三行
    col7, col8, col9 = st.columns(3, gap="small")

    # 格子索引与列对应关系
    grid_cols = [col1, col2, col3, col4, col5, col6, col7, col8, col9]

    # 生成九宫格按钮
    for grid_idx in range(9):
        with grid_cols[grid_idx]:
            btn_text = st.session_state.board[grid_idx] if st.session_state.board[grid_idx] != "" else " "
            is_disabled = (
                    st.session_state.game_over
                    or st.session_state.board[grid_idx] != ""
                    or st.session_state.player_count < 2
            )

            if st.button(
                    btn_text,
                    key=f"btn_{room_id}_{grid_idx}",
                    disabled=is_disabled,
                    use_container_width=True,
                    type="primary" if st.session_state.board[grid_idx] == "X" else "secondary"
            ):
                st.session_state.board[grid_idx] = st.session_state.current_player
                st.session_state.winner = check_winner(st.session_state.board)
                if st.session_state.winner is not None:
                    st.session_state.game_over = True
                else:
                    st.session_state.current_player = "O" if st.session_state.current_player == "X" else "X"

                save_game_state({
                    "object_id": st.session_state.object_id,
                    "room_id": room_id,
                    "board": st.session_state.board,
                    "current_player": st.session_state.current_player,
                    "game_over": st.session_state.game_over,
                    "winner": st.session_state.winner,
                    "player_count": st.session_state.player_count
                })
                st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)


# ---------------------- 9. 重置游戏 ----------------------
def reset_game():
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
        "player_count": st.session_state.player_count
    })
    st.rerun()


if st.session_state.player_count >= 2:
    st.divider()
    st.button("🔄 重新开始本局", on_click=reset_game, use_container_width=True)

st.caption(f"""
💡 规则：
1. 每个房间最多2人，满人后无法加入
2. 已落子的格子会被锁定，不可重复点击
3. 两人轮流落子（X→O→X...），直到分出胜负
当前房间：{room_id} | 状态：{st.session_state.player_count}/2人
""")