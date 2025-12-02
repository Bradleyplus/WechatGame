import streamlit as st
import requests
import time

# ---------------------- 页面样式优化（缩小格子+手机适配） ----------------------
st.set_page_config(
    page_title="双人井字棋",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# 核心修改：缩小格子大小，确保手机显示3x3紧凑九宫格
st.markdown("""
<style>
    .board-container {
        width: 100%;
        max-width: 240px;  # 缩小棋盘整体宽度
        margin: 0 auto;
    }
    .stButton > button {
        width: 100% !important;
        height: 60px !important;  # 缩小按钮高度
        font-size: 1.5rem !important;  # 缩小字体
        padding: 0 !important;
        margin: 1px !important;  # 减小格子间距
    }
    /* 手机端强制紧凑显示 */
    @media (max-width: 400px) {
        .board-container {
            max-width: 210px;
        }
        .stButton > button {
            height: 50px !important;
            font-size: 1.2rem !important;
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


# ---------------------- 3. 读取房间状态 ----------------------
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
                "player_count": game_data.get("player_count", 0)
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


# ---------------------- 4. 保存房间状态（修复400错误） ----------------------
def save_game_state(state):
    if state["object_id"] == "local":
        st.warning("本地模式：仅本机可见操作")
        return
    try:
        # 严格验证数据格式（解决400错误核心）
        valid_board = state["board"] if isinstance(state["board"], list) else ["", "", "", "", "", "", "", "", ""]
        update_url = f"{BASE_API_URL}/{state['object_id']}"
        update_data = {
            "room_id": str(state["room_id"]),  # 强制字符串类型
            "board": valid_board,
            "current_player": str(state["current_player"]),  # 强制字符串
            "game_over": bool(state["game_over"]),  # 强制布尔值
            "winner": state["winner"] if state["winner"] in ("X", "O", "平局", None) else None,
            "player_count": max(0, min(2, int(state["player_count"])))  # 强制0-2范围
        }
        response = requests.put(update_url, headers=HEADERS, json=update_data, timeout=10)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        st.warning(f"同步失败：{str(e)}")


# ---------------------- 5. 房间管理（进入/退出） ----------------------
def enter_room(room_id, current_state):
    if current_state["player_count"] < 2:
        return {**current_state, "player_count": current_state["player_count"] + 1}
    return current_state


def exit_room(room_id, current_state):
    if current_state["player_count"] > 0:
        return {**current_state, "player_count": current_state["player_count"] - 1}
    return current_state


# ---------------------- 6. 页面初始化 ----------------------
st.title("🎮 双人井字棋（联机版）")

# 房间选择
room_id = st.selectbox(
    "🔑 选择游戏房间",
    options=["8888", "6666"],
    index=0,
    key="room_selector"
)

# 初始化会话状态
if "entered_room" not in st.session_state:
    st.session_state.entered_room = False
if "object_id" not in st.session_state:
    st.session_state.object_id = ""

# 手动刷新按钮（核心：取消自动刷新，改为手动）
col_refresh, col_exit = st.columns(2)
with col_refresh:
    if st.button("🔄 刷新状态", use_container_width=True):
        game_state = load_game_state(room_id)
        st.session_state.board = game_state["board"]
        st.session_state.current_player = game_state["current_player"]
        st.session_state.game_over = game_state["game_over"]
        st.session_state.winner = game_state["winner"]
        st.session_state.player_count = game_state["player_count"]
        st.session_state.object_id = game_state["object_id"]

# 手动退出房间按钮
with col_exit:
    if st.button("🚪 退出房间", use_container_width=True):
        if st.session_state.entered_room:
            # 退出时更新人数
            current_state = {
                "object_id": st.session_state.object_id,
                "room_id": room_id,
                "player_count": st.session_state.player_count
            }
            exited_state = exit_room(room_id, current_state)
            save_game_state(exited_state)
            # 重置会话状态
            st.session_state.entered_room = False
            st.session_state.board = ["", "", "", "", "", "", "", "", ""]
            st.session_state.player_count = 0
            st.success("已退出房间")
            st.rerun()

# 进入房间按钮
if not st.session_state.entered_room:
    if st.button("📥 进入房间", use_container_width=True):
        game_state = load_game_state(room_id)
        if game_state["player_count"] < 2:
            entered_state = enter_room(room_id, game_state)
            save_game_state(entered_state)
            st.session_state.entered_room = True
            st.session_state.object_id = entered_state["object_id"]
            st.session_state.board = entered_state["board"]
            st.session_state.current_player = entered_state["current_player"]
            st.session_state.game_over = entered_state["game_over"]
            st.session_state.winner = entered_state["winner"]
            st.session_state.player_count = entered_state["player_count"]
            st.success(f"已进入房间 {room_id}")
            st.rerun()
        else:
            st.error("房间已满！请选择其他房间或等待")

# 已进入房间时显示状态
if st.session_state.entered_room:
    st.divider()
    # 房间状态提示
    if st.session_state.player_count < 2:
        st.info(f"📌 房间 {room_id} - 等待玩家加入（当前{st.session_state.player_count}/2人）")
    else:
        st.info(f"📌 房间 {room_id} - 已满（2/2人）| 当前回合：玩家 {st.session_state.current_player}")

    # 游戏结束提示
    if st.session_state.game_over:
        if st.session_state.winner == "平局":
            st.success(f"🟰 游戏结束：平局！")
        else:
            st.success(f"🏆 游戏结束：玩家 {st.session_state.winner} 获胜！")

    # ---------------------- 7. 九宫格棋盘（缩小后版本） ----------------------
    st.subheader("游戏棋盘")
    with st.container():
        st.markdown('<div class="board-container">', unsafe_allow_html=True)

        # 3x3网格（原生columns确保紧凑）
        row1 = st.columns(3, gap="small")
        row2 = st.columns(3, gap="small")
        row3 = st.columns(3, gap="small")
        grid_cols = [row1[0], row1[1], row1[2], row2[0], row2[1], row2[2], row3[0], row3[1], row3[2]]

        # 生成棋盘按钮
        for grid_idx in range(9):
            with grid_cols[grid_idx]:
                btn_text = st.session_state.board[grid_idx] if st.session_state.board[grid_idx] != "" else " "
                is_disabled = (
                        not st.session_state.entered_room  # 未进入房间禁用
                        or st.session_state.game_over
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
                    # 落子逻辑
                    st.session_state.board[grid_idx] = st.session_state.current_player
                    st.session_state.winner = check_winner(st.session_state.board)
                    if st.session_state.winner is not None:
                        st.session_state.game_over = True
                    else:
                        st.session_state.current_player = "O" if st.session_state.current_player == "X" else "X"

                    # 保存状态
                    save_game_state({
                        "object_id": st.session_state.object_id,
                        "room_id": room_id,
                        "board": st.session_state.board,
                        "current_player": st.session_state.current_player,
                        "game_over": st.session_state.game_over,
                        "winner": st.session_state.winner,
                        "player_count": st.session_state.player_count
                    })
                    st.success("落子成功！请对方刷新状态")
                    st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)

    # 重置游戏按钮
    if st.session_state.player_count >= 2:
        st.divider()


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


        st.button("🔄 重新开始本局", on_click=reset_game, use_container_width=True)

# 操作说明
st.caption("""
💡 操作指南：
1. 选择房间后点击「进入房间」（最多2人）
2. 落子后请对方点击「刷新状态」查看
3. 已落子格子锁定，不可重复点击
4. 点击「退出房间」可离开当前游戏
""")