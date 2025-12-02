import streamlit as st
import requests
import uuid  # 用于生成设备唯一标识

# ---------------------- 页面样式优化（确保手机九宫格显示） ----------------------
st.set_page_config(
    page_title="双人井字棋",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# 关键：最小化格子尺寸，强制3x3不换行
st.markdown("""
<style>
    .board-container {
        width: 100% !important;
        max-width: 210px !important;  # 手机适配的最小宽度
        margin: 0 auto !important;
    }
    .stButton > button {
        width: 100% !important;
        height: 60px !important;
        font-size: 1.5rem !important;
        padding: 0 !important;
        margin: 1px !important;
        white-space: nowrap !important;  # 防止文字换行导致格子变形
    }
    /* 手机端强制紧凑布局 */
    @media (max-width: 400px) {
        .board-container {
            max-width: 180px !important;
        }
        .stButton > button {
            height: 50px !important;
            font-size: 1.2rem !important;
        }
    }
    /* 确保列不换行 */
    .stColumns {
        flex-wrap: nowrap !important;
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


# ---------------------- 3. 读取房间状态（确保棋盘同步） ----------------------
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
                "board": game_data.get("board", ["", "", "", "", "", "", "", "", ""]),  # 强制列表
                "current_player": game_data.get("current_player", "X"),
                "game_over": game_data.get("game_over", False),
                "winner": game_data.get("winner"),
                "room_id": room_id,
                "player_count": game_data.get("player_count", 0),
                "players": game_data.get("players", {})  # 新增：存储玩家角色（设备ID→X/O）
            }
        else:
            # 新房间初始化（包含玩家角色映射）
            init_game = {
                "room_id": room_id,
                "board": ["", "", "", "", "", "", "", "", ""],
                "current_player": "X",
                "game_over": False,
                "winner": None,
                "player_count": 0,
                "players": {}  # 设备ID: 角色（X/O）
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
                "player_count": 0,
                "players": {}
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
            "player_count": 0,
            "players": {}
        }


# ---------------------- 4. 保存房间状态（修复退出错误） ----------------------
def save_game_state(state):
    if state["object_id"] == "local":
        st.warning("本地模式：仅本机可见操作")
        return
    try:
        # 确保所有字段存在且格式正确（解决KeyError）
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
            "players": state.get("players", {})  # 保存玩家角色映射
        }
        update_url = f"{BASE_API_URL}/{state['object_id']}"
        response = requests.put(update_url, headers=HEADERS, json=valid_fields, timeout=10)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        st.warning(f"同步失败：{str(e)}")


# ---------------------- 5. 房间管理（进入/退出/角色分配） ----------------------
def get_device_id():
    """生成设备唯一标识（确保角色固定）"""
    if "device_id" not in st.session_state:
        st.session_state.device_id = str(uuid.uuid4())  # 每次设备生成唯一ID
    return st.session_state.device_id


def enter_room(room_id, current_state):
    """进入房间并分配角色（1人→X，2人→O）"""
    device_id = get_device_id()
    players = current_state["players"].copy()
    player_count = current_state["player_count"]

    # 已在房间中则不重新分配
    if device_id in players:
        return current_state

    # 分配角色：第1人→X，第2人→O
    if player_count < 1:
        players[device_id] = "X"
    elif player_count < 2:
        players[device_id] = "O"

    return {
        **current_state,
        "player_count": min(player_count + 1, 2),
        "players": players
    }


def exit_room(room_id, current_state):
    """退出房间并清理角色"""
    device_id = get_device_id()
    players = current_state["players"].copy()
    player_count = current_state["player_count"]

    # 移除当前设备的角色
    if device_id in players:
        del players[device_id]
        player_count = max(0, player_count - 1)

    # 退出时保留棋盘状态，但更新人数和角色
    return {
        **current_state,
        "player_count": player_count,
        "players": players,
        "board": current_state.get("board", ["", "", "", "", "", "", "", "", ""]),  # 确保包含board字段
        "current_player": current_state.get("current_player", "X"),
        "game_over": current_state.get("game_over", False),
        "winner": current_state.get("winner")
    }


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
if "device_id" not in st.session_state:
    st.session_state.device_id = str(uuid.uuid4())  # 设备唯一ID
if "my_role" not in st.session_state:
    st.session_state.my_role = None  # 我的角色（X/O）

# 操作按钮：刷新/退出
col_refresh, col_exit = st.columns(2)
with col_refresh:
    refresh_clicked = st.button("🔄 刷新状态", use_container_width=True)
with col_exit:
    exit_clicked = st.button("🚪 退出房间", use_container_width=True)

# 处理退出房间（修复KeyError）
if exit_clicked and st.session_state.entered_room:
    # 拉取当前状态，确保包含所有字段
    current_state = load_game_state(room_id)
    # 构造完整的退出状态（包含所有必要字段）
    exited_state = exit_room(room_id, current_state)
    save_game_state(exited_state)
    # 重置本地状态
    st.session_state.entered_room = False
    st.session_state.my_role = None
    st.success("已退出房间")
    st.rerun()

# 进入房间按钮
if not st.session_state.entered_room:
    if st.button("📥 进入房间", use_container_width=True):
        game_state = load_game_state(room_id)
        if game_state["player_count"] < 2:
            entered_state = enter_room(room_id, game_state)
            save_game_state(entered_state)
            # 记录我的角色
            st.session_state.my_role = entered_state["players"].get(st.session_state.device_id)
            st.session_state.entered_room = True
            st.success(f"已进入房间 {room_id}，您的角色：{st.session_state.my_role}")
            st.rerun()
        else:
            st.error("房间已满！请选择其他房间")

# 已进入房间：显示棋盘和状态
if st.session_state.entered_room:
    # 刷新状态时强制从云端拉取（解决棋子位置变化）
    if refresh_clicked:
        game_state = load_game_state(room_id)
        st.session_state.board = game_state["board"]
        st.session_state.current_player = game_state["current_player"]
        st.session_state.game_over = game_state["game_over"]
        st.session_state.winner = game_state["winner"]
        st.session_state.player_count = game_state["player_count"]
        st.session_state.players = game_state["players"]
        # 更新我的角色（防止角色丢失）
        st.session_state.my_role = game_state["players"].get(st.session_state.device_id)
        st.success("状态已刷新")

    # 拉取最新状态（首次进入时）
    if "board" not in st.session_state:
        game_state = load_game_state(room_id)
        st.session_state.board = game_state["board"]
        st.session_state.current_player = game_state["current_player"]
        st.session_state.game_over = game_state["game_over"]
        st.session_state.winner = game_state["winner"]
        st.session_state.player_count = game_state["player_count"]
        st.session_state.players = game_state["players"]

    # 显示房间状态
    st.divider()
    st.info(f"""
    📌 房间 {room_id}（{st.session_state.player_count}/2人）
    您的角色：{st.session_state.my_role} | 当前回合：{st.session_state.current_player}
    """)

    # 游戏结束提示
    if st.session_state.game_over:
        if st.session_state.winner == "平局":
            st.success("🟰 游戏结束：平局！")
        else:
            st.success(f"🏆 游戏结束：玩家 {st.session_state.winner} 获胜！")

    # ---------------------- 7. 九宫格棋盘（确保手机显示） ----------------------
    st.subheader("游戏棋盘")
    with st.container():
        st.markdown('<div class="board-container">', unsafe_allow_html=True)

        # 3x3网格（强制不换行）
        row1 = st.columns(3, gap="small")
        row2 = st.columns(3, gap="small")
        row3 = st.columns(3, gap="small")
        grid_cols = [row1[0], row1[1], row1[2], row2[0], row2[1], row2[2], row3[0], row3[1], row3[2]]

        # 生成棋盘按钮
        for grid_idx in range(9):
            with grid_cols[grid_idx]:
                btn_text = st.session_state.board[grid_idx] if st.session_state.board[grid_idx] != "" else " "
                # 禁用条件：非自己回合/已落子/游戏结束
                is_disabled = (
                        st.session_state.game_over
                        or st.session_state.board[grid_idx] != ""
                        or st.session_state.my_role != st.session_state.current_player  # 只有当前角色可落子
                )

                if st.button(
                        btn_text,
                        key=f"btn_{room_id}_{grid_idx}",
                        disabled=is_disabled,
                        use_container_width=True,
                        type="primary" if st.session_state.board[grid_idx] == "X" else "secondary"
                ):
                    # 落子（只能用自己的角色）
                    st.session_state.board[grid_idx] = st.session_state.my_role
                    # 判断胜负
                    st.session_state.winner = check_winner(st.session_state.board)
                    if st.session_state.winner is not None:
                        st.session_state.game_over = True
                        st.session_state.current_player = None  # 游戏结束无当前玩家
                    else:
                        # 切换回合（X→O，O→X）
                        st.session_state.current_player = "O" if st.session_state.current_player == "X" else "X"

                    # 保存状态到云端
                    save_game_state({
                        "object_id": st.session_state.get("object_id", ""),
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

    # 重置游戏按钮
    if st.button("🔄 重新开始本局", use_container_width=True):
        reset_board = ["", "", "", "", "", "", "", "", ""]
        st.session_state.board = reset_board
        st.session_state.current_player = "X"
        st.session_state.game_over = False
        st.session_state.winner = None
        save_game_state({
            "object_id": st.session_state.get("object_id", ""),
            "room_id": room_id,
            "board": reset_board,
            "current_player": "X",
            "game_over": False,
            "winner": None,
            "player_count": st.session_state.player_count,
            "players": st.session_state.players
        })
        st.rerun()

# 操作说明
st.caption("""
💡 操作指南：
1. 选择房间→点击「进入房间」（最多2人，自动分配X/O角色）
2. 只能在自己的回合落子（X/O轮流）
3. 落子后请对方点击「刷新状态」查看
4. 已落子格子锁定，不可修改
5. 点击「退出房间」可离开游戏
""")