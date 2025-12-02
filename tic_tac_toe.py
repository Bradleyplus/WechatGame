import streamlit as st
import requests
import time
from streamlit_extras.grid import grid  # 用于响应式网格布局

# ---------------------- 页面样式优化（解决手机九宫格显示问题） ----------------------
st.set_page_config(
    page_title="双人井字棋",
    layout="centered",  # 居中布局，适配手机
    initial_sidebar_state="collapsed"  # 隐藏侧边栏，节省空间
)

# 自定义CSS：强制按钮正方形显示，适配手机屏幕
st.markdown("""
<style>
    .stButton > button {
        width: 100% !important;
        height: 80px !important;  # 固定高度，确保正方形
        font-size: 2rem !important;  # 棋子大小适配手机
        padding: 0 !important;
    }
    @media (max-width: 600px) {  # 手机端额外调整
        .stButton > button {
            height: 60px !important;
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


# ---------------------- 3. 读取房间状态（新增人数限制） ----------------------
def load_game_state(room_id):
    try:
        params = {"where": f'{{"room_id":"{room_id}"}}', "limit": 1}
        response = requests.get(BASE_API_URL, headers=HEADERS, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data.get("results"):
            game_data = data["results"][0]
            # 确保返回玩家数量（兼容旧数据）
            player_count = game_data.get("player_count", 0)
            return {
                "object_id": game_data["objectId"],
                "board": game_data["board"],
                "current_player": game_data["current_player"],
                "game_over": game_data["game_over"],
                "winner": game_data["winner"],
                "room_id": room_id,
                "player_count": player_count  # 新增：房间当前人数
            }
        else:
            # 新房间初始化（包含人数计数）
            init_game = {
                "room_id": room_id,
                "board": ["", "", "", "", "", "", "", "", ""],
                "current_player": "X",
                "game_over": False,
                "winner": None,
                "player_count": 0  # 初始人数为0
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


# ---------------------- 4. 保存房间状态（同步人数和落子） ----------------------
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
            "player_count": state["player_count"]  # 保存人数
        }
        response = requests.put(update_url, headers=HEADERS, json=update_data, timeout=10)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        st.warning(f"同步失败：{str(e)}")


# ---------------------- 5. 房间人数管理（限制2人进入） ----------------------
def enter_room(room_id, current_state):
    """处理玩家进入房间，限制最多2人"""
    if current_state["player_count"] < 2:
        # 人数未满，允许进入并增加计数
        new_count = current_state["player_count"] + 1
        return {**current_state, "player_count": new_count}
    else:
        # 人数已满，返回原状态
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
# 玩家进入房间（首次进入时人数+1，重复进入不计数）
if "entered_room" not in st.session_state:
    game_state = enter_room(room_id, game_state)
    save_game_state(game_state)
    st.session_state.entered_room = True  # 标记为已进入

# 更新本地状态
st.session_state.object_id = game_state["object_id"]
st.session_state.board = game_state["board"]
st.session_state.current_player = game_state["current_player"]
st.session_state.game_over = game_state["game_over"]
st.session_state.winner = game_state["winner"]
st.session_state.room_id = room_id
st.session_state.player_count = game_state["player_count"]

# ---------------------- 7. 房间状态提示（显示人数和回合） ----------------------
st.divider()
# 显示房间人数状态
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

# ---------------------- 8. 响应式九宫格棋盘（核心修复手机显示） ----------------------
st.subheader("游戏棋盘")
# 使用streamlit-extras的grid组件，强制3x3网格（适配手机）
board_grid = grid(3, 3, vertical_align="center")  # 3列3行，垂直居中

# 遍历格子生成按钮
for grid_idx in range(9):
    # 按钮文本：X/O或空白（手机端清晰显示）
    btn_text = st.session_state.board[grid_idx] if st.session_state.board[grid_idx] != "" else " "
    # 禁用条件：已落子/游戏结束/房间未满（确保两人才能开始）
    is_disabled = (
            st.session_state.game_over
            or st.session_state.board[grid_idx] != ""
            or st.session_state.player_count < 2  # 人数不足2人时禁止落子
    )

    # 在网格中放置按钮
    if board_grid.button(
            btn_text,
            key=f"btn_{room_id}_{grid_idx}",
            disabled=is_disabled,
            use_container_width=True,
            type="primary" if st.session_state.board[grid_idx] == "X" else "secondary"
    ):
        # 落子逻辑
        st.session_state.board[grid_idx] = st.session_state.current_player
        # 判断胜负
        st.session_state.winner = check_winner(st.session_state.board)
        if st.session_state.winner is not None:
            st.session_state.game_over = True
        else:
            # 切换玩家
            st.session_state.current_player = "O" if st.session_state.current_player == "X" else "X"

        # 保存状态（包含当前人数）
        save_game_state({
            "object_id": st.session_state.object_id,
            "room_id": room_id,
            "board": st.session_state.board,
            "current_player": st.session_state.current_player,
            "game_over": st.session_state.game_over,
            "winner": st.session_state.winner,
            "player_count": st.session_state.player_count
        })

        # 立即刷新
        st.rerun()


# ---------------------- 9. 重置游戏 ----------------------
def reset_game():
    reset_board = ["", "", "", "", "", "", "", "", ""]
    st.session_state.board = reset_board
    st.session_state.current_player = "X"
    st.session_state.game_over = False
    st.session_state.winner = None

    # 重置时保留人数（不踢人）
    save_game_state({
        "object_id": st.session_state.object_id,
        "room_id": room_id,
        "board": reset_board,
        "current_player": "X",
        "game_over": False,
        "winner": None,
        "player_count": st.session_state.player_count  # 保留当前人数
    })
    st.rerun()


# 只有房间满人时才显示重置按钮
if st.session_state.player_count >= 2:
    st.divider()
    st.button("🔄 重新开始本局", on_click=reset_game, use_container_width=True)

# 联机说明
st.caption(f"""
💡 规则：
1. 每个房间最多2人，满人后无法加入
2. 已落子的格子会被锁定，不可重复点击
3. 两人轮流落子（X→O→X...），直到分出胜负
当前房间：{room_id} | 状态：{st.session_state.player_count}/2人
""")