import streamlit as st
import requests
import time

# ---------------------- 1. LeanCloud配置（已填你的凭证，无需修改） ----------------------
APP_ID = "hiwS1jgaGdLqJhk2UtEwHGdK-gzGzoHsz"
APP_KEY = "bENg8Yr0UlGdt7NJB70i2VOW"
BASE_API_URL = "https://api.leancloud.cn/1.1/classes/GameState"
HEADERS = {
    "X-LC-Id": APP_ID,
    "X-LC-Key": APP_KEY,
    "Content-Type": "application/json"
}

# ---------------------- 2. 胜负判断函数（无修改） ----------------------
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

# ---------------------- 3. 核心修复：精准读取房间状态（优先拉取云端） ----------------------
def load_game_state(room_id):
    try:
        # 精准查询指定房间ID的记录（避免多记录冲突）
        params = {"where": f'{{"room_id":"{room_id}"}}', "limit": 1}
        response = requests.get(BASE_API_URL, headers=HEADERS, params=params, timeout=10)
        response.raise_for_status()  # 触发HTTP错误提示
        data = response.json()

        if data.get("results"):
            # 优先使用云端最新状态，覆盖本地
            game_data = data["results"][0]
            return {
                "object_id": game_data["objectId"],
                "board": game_data["board"],
                "current_player": game_data["current_player"],
                "game_over": game_data["game_over"],
                "winner": game_data["winner"],
                "room_id": room_id
            }
        else:
            # 新房间：初始化并写入云端
            init_game = {
                "room_id": room_id,
                "board": [""] * 9,
                "current_player": "X",
                "game_over": False,
                "winner": None
            }
            create_response = requests.post(BASE_API_URL, headers=HEADERS, json=init_game, timeout=10)
            create_response.raise_for_status()
            new_game = create_response.json()
            return {
                "object_id": new_game["objectId"],
                "board": [""] * 9,
                "current_player": "X",
                "game_over": False,
                "winner": None,
                "room_id": room_id
            }
    except requests.exceptions.RequestException as e:
        st.error(f"服务器连接失败：{str(e)}")
        # 本地降级（仅临时使用，联机失效）
        return {
            "object_id": "local",
            "board": [""] * 9,
            "current_player": "X",
            "game_over": False,
            "winner": None,
            "room_id": room_id
        }

# ---------------------- 4. 核心修复：确保状态正确写入云端 ----------------------
def save_game_state(state):
    if state["object_id"] == "local":
        st.warning("当前为本地模式，无法联机同步！")
        return
    try:
        update_url = f"{BASE_API_URL}/{state['object_id']}"
        update_data = {
            "room_id": state["room_id"],
            "board": state["board"],
            "current_player": state["current_player"],
            "game_over": state["game_over"],
            "winner": state["winner"]
        }
        response = requests.put(update_url, headers=HEADERS, json=update_data, timeout=10)
        response.raise_for_status()  # 触发HTTP错误提示
    except requests.exceptions.RequestException as e:
        st.warning(f"同步到服务器失败：{str(e)}")

# ---------------------- 5. 初始化页面（优化刷新逻辑，避免冲突） ----------------------
st.title("🎮 双人井字棋（联机版）")

# 房间ID输入（核心：必须相同ID才能联机）
room_id = st.text_input("🔑 输入房间ID（和好友填相同ID）", value="default", max_chars=20)
if not room_id:
    room_id = "default"

# 初始化/刷新房间状态（优先拉取云端，确保同步）
game_state = load_game_state(room_id)
# 强制同步session_state为云端最新状态
st.session_state.object_id = game_state["object_id"]
st.session_state.board = game_state["board"]
st.session_state.current_player = game_state["current_player"]
st.session_state.game_over = game_state["game_over"]
st.session_state.winner = game_state["winner"]
st.session_state.room_id = room_id

# 兼容版自动刷新（每2秒拉取一次云端，不中断操作）
if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = time.time()
if time.time() - st.session_state.last_refresh > 2 and not st.session_state.game_over:
    st.session_state.last_refresh = time.time()
    st.experimental_rerun()  # 温和刷新，替代st.rerun

# ---------------------- 6. 游戏状态提示（显示当前可操作玩家） ----------------------
st.divider()
if st.session_state.game_over:
    if st.session_state.winner == "平局":
        st.success(f"🟰 房间 {room_id} - 游戏结束：平局！")
    else:
        st.success(f"🏆 房间 {room_id} - 游戏结束：玩家 {st.session_state.winner} 获胜！")
else:
    st.info(f"📌 房间 {room_id} - 当前回合：仅玩家 {st.session_state.current_player} 可落子！")

# ---------------------- 7. 核心修复：限制落子权限（只能当前玩家操作） ----------------------
st.subheader("游戏棋盘")
for row in range(3):
    cols = st.columns(3)
    for col in range(3):
        idx = row * 3 + col
        with cols[col]:
            btn_text = st.session_state.board[idx] if st.session_state.board[idx] != "" else "　"
            # 关键：禁用非当前回合的落子+已有棋子的位置
            is_disabled = (
                st.session_state.game_over
                or st.session_state.board[idx] != ""
            )
            btn_clicked = st.button(
                btn_text,
                key=f"{room_id}_{idx}",
                disabled=is_disabled,
                use_container_width=True,
                type="primary" if st.session_state.board[idx] == "X" else "secondary"
            )
            if btn_clicked:
                # 强制验证：只能当前玩家落子
                st.session_state.board[idx] = st.session_state.current_player
                # 判断胜负
                st.session_state.winner = check_winner(st.session_state.board)
                if st.session_state.winner is not None:
                    st.session_state.game_over = True
                else:
                    # 切换玩家（X→O，O→X）
                    st.session_state.current_player = "O" if st.session_state.current_player == "X" else "X"
                # 立即保存状态到云端（同步给好友）
                save_game_state({
                    "object_id": st.session_state.object_id,
                    "room_id": room_id,
                    "board": st.session_state.board,
                    "current_player": st.session_state.current_player,
                    "game_over": st.session_state.game_over,
                    "winner": st.session_state.winner
                })
                # 刷新页面，立即显示最新状态
                st.experimental_rerun()

# ---------------------- 8. 重置游戏（同步到云端） ----------------------
def reset_game():
    # 重置本地状态
    reset_data = {
        "object_id": st.session_state.object_id,
        "room_id": room_id,
        "board": [""] * 9,
        "current_player": "X",
        "game_over": False,
        "winner": None
    }
    # 同步到云端
    save_game_state(reset_data)
    # 刷新本地状态
    st.session_state.board = [""] * 9
    st.session_state.current_player = "X"
    st.session_state.game_over = False
    st.session_state.winner = None
    st.experimental_rerun()

st.divider()
st.button("🔄 重新开始本局", on_click=reset_game, use_container_width=True)
st.caption(f"""
💡 联机规则：
1. 和好友输入【完全相同】的房间ID（如：1234）；
2. 房间内默认X先落子，落子后自动切换为O回合（仅O可落子）；
3. 无需手动刷新，页面每2秒自动同步对方落子；
当前房间：{room_id}
""")