import streamlit as st
import requests  # 用于调用LeanCloud REST API，无编译依赖

# ---------------------- 1. 核心配置（必须替换为你的LeanCloud信息） ----------------------
# 替换成你在LeanCloud「应用凭证」中获取的App ID和App Key
APP_ID = "hiwS1jgaGdLqJhk2UtEwHGdK-gzGzoHsz"
APP_KEY = "bENg8Yr0UlGdt7NJB70i2VOW"
# LeanCloud REST API地址（GameState是你创建的数据表名，无需修改）
BASE_API_URL = "https://api.leancloud.cn/1.1/classes/GameState"
# LeanCloud API请求头（固定格式，无需修改）
HEADERS = {
    "X-LC-Id": APP_ID,
    "X-LC-Key": APP_KEY,
    "Content-Type": "application/json"
}


# ---------------------- 2. 井字棋胜负判断函数（核心补充） ----------------------
def check_winner():
    board = st.session_state.board
    # 定义胜利组合：3行、3列、2条对角线
    win_combinations = [
        [0, 1, 2], [3, 4, 5], [6, 7, 8],  # 行
        [0, 3, 6], [1, 4, 7], [2, 5, 8],  # 列
        [0, 4, 8], [2, 4, 6]  # 对角线
    ]
    # 检查是否有玩家获胜
    for combo in win_combinations:
        a, b, c = combo
        if board[a] == board[b] == board[c] != "":
            return board[a]  # 返回赢家（X或O）
    # 检查是否平局（棋盘满且无赢家）
    if "" not in board:
        return "平局"
    # 游戏未结束
    return None


# ---------------------- 3. 从LeanCloud读取游戏状态（双人同步核心） ----------------------
def load_game_state():
    try:
        # 发送GET请求获取游戏状态
        response = requests.get(BASE_API_URL, headers=HEADERS, timeout=10)
        data = response.json()

        if data.get("results"):  # 表中有数据，读取第一条（单局游戏）
            game_data = data["results"][0]
            return {
                "object_id": game_data["objectId"],  # 数据ID，用于后续更新
                "board": game_data["board"],
                "current_player": game_data["current_player"],
                "game_over": game_data["game_over"],
                "winner": game_data["winner"]
            }
        else:  # 表为空，初始化新游戏并保存到LeanCloud
            init_game = {
                "board": [""] * 9,
                "current_player": "X",
                "game_over": False,
                "winner": None
            }
            create_response = requests.post(BASE_API_URL, json=init_game, headers=HEADERS, timeout=10)
            new_game = create_response.json()
            return {
                "object_id": new_game["objectId"],
                "board": [""] * 9,
                "current_player": "X",
                "game_over": False,
                "winner": None
            }
    except Exception as e:
        st.error(f"连接LeanCloud失败：{str(e)}")
        # 本地降级方案（仅临时使用，双人同步会失效）
        return {
            "object_id": "local_temp",
            "board": [""] * 9,
            "current_player": "X",
            "game_over": False,
            "winner": None
        }


# ---------------------- 4. 保存游戏状态到LeanCloud ----------------------
def save_game_state(state):
    try:
        # 跳过本地临时ID的保存（仅LeanCloud数据需要更新）
        if state["object_id"] == "local_temp":
            return
        # 发送PUT请求更新数据
        update_url = f"{BASE_API_URL}/{state['object_id']}"
        update_data = {
            "board": state["board"],
            "current_player": state["current_player"],
            "game_over": state["game_over"],
            "winner": state["winner"]
        }
        requests.put(update_url, json=update_data, headers=HEADERS, timeout=10)
    except Exception as e:
        st.warning(f"同步数据到LeanCloud失败：{str(e)}")


# ---------------------- 5. 初始化游戏状态 ----------------------
if "object_id" not in st.session_state:
    game_state = load_game_state()
    st.session_state.object_id = game_state["object_id"]
    st.session_state.board = game_state["board"]
    st.session_state.current_player = game_state["current_player"]
    st.session_state.game_over = game_state["game_over"]
    st.session_state.winner = game_state["winner"]

# ---------------------- 6. 页面UI（微信适配的3x3棋盘） ----------------------
st.title("🎮 双人井字棋（Bradley）")

# 显示当前玩家/胜负结果
if st.session_state.game_over:
    if st.session_state.winner == "score draw":
        st.success("🟰 游戏结束：score draw！")
    else:
        st.success(f"🏆 游戏结束：玩家 {st.session_state.winner} WIN！")
else:
    st.info(f"当前回合：玩家 {st.session_state.current_player}")

# 3x3棋盘（手机/微信适配）
st.subheader("游戏棋盘")
for row in range(3):
    cols_in_row = st.columns(3)  # 每行3列，强制3x3布局
    for col in range(3):
        grid_index = row * 3 + col
        with cols_in_row[col]:
            # 按钮显示X/O，空位置显示空格（避免按钮太小）
            btn_text = st.session_state.board[grid_index] if st.session_state.board[grid_index] != "" else "　"
            # 创建按钮（游戏结束/已有棋子时禁用）
            btn_clicked = st.button(
                btn_text,
                key=grid_index,
                disabled=st.session_state.game_over or st.session_state.board[grid_index] != "",
                use_container_width=True,  # 适配手机屏幕宽度
                type="primary" if st.session_state.board[grid_index] == "X" else "secondary"
            )
            # 按钮点击逻辑
            if btn_clicked:
                # 落子
                st.session_state.board[grid_index] = st.session_state.current_player
                # 判断胜负
                st.session_state.winner = check_winner()
                if st.session_state.winner is not None:
                    st.session_state.game_over = True
                else:
                    # 切换玩家
                    st.session_state.current_player = "O" if st.session_state.current_player == "X" else "X"
                # 同步状态到LeanCloud
                save_game_state({
                    "object_id": st.session_state.object_id,
                    "board": st.session_state.board,
                    "current_player": st.session_state.current_player,
                    "game_over": st.session_state.game_over,
                    "winner": st.session_state.winner
                })
                # 刷新页面显示最新状态
                st.rerun()


# 重置游戏按钮
def reset_game():
    # 重置本地状态
    st.session_state.board = [""] * 9
    st.session_state.current_player = "X"
    st.session_state.game_over = False
    st.session_state.winner = None
    # 同步重置LeanCloud数据
    save_game_state({
        "object_id": st.session_state.object_id,
        "board": [""] * 9,
        "current_player": "X",
        "game_over": False,
        "winner": None
    })


st.button("🔄 重新开始游戏", on_click=reset_game, use_container_width=True)

# 底部提示
st.caption("💡 微信打开即可双人同步玩，一人落子后另一人刷新页面可见！")