import streamlit as st
import requests
import time

# ---------------------- 1. LeanCloud配置（已填你的凭证） ----------------------
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

# ---------------------- 3. 读取房间状态（优先云端） ----------------------
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
                "board": game_data["board"],
                "current_player": game_data["current_player"],
                "game_over": game_data["game_over"],
                "winner": game_data["winner"],
                "room_id": room_id
            }
        else:
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
        return {
            "object_id": "local",
            "board": [""] * 9,
            "current_player": "X",
            "game_over": False,
            "winner": None,
            "room_id": room_id
        }

# ---------------------- 4. 保存房间状态 ----------------------
def save_game_state(state):
    if state["object_id"] == "local":
        st.warning("本地模式无法联机同步！")
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
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        st.warning(f"同步失败：{str(e)}")

# ---------------------- 5. 页面初始化与刷新 ----------------------
st.title("🎮 双人井字棋（联机版）")

# 房间ID输入
room_id = st.text_input("🔑 输入房间ID（和好友填相同ID）", value="8888", max_chars=20)
if not room_id:
    room_id = "default"

# 拉取云端最新状态
game_state = load_game_state(room_id)
st.session_state.object_id = game_state["object_id"]
st.session_state.board = game_state["board"]
st.session_state.current_player = game_state["current_player"]
st.session_state.game_over = game_state["game_over"]
st.session_state.winner = game_state["winner"]
st.session_state.room_id = room_id

# 自动刷新（每2秒拉取一次，避免频繁刷新）
if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = time.time()
if time.time() - st.session_state.last_refresh > 2 and not st.session_state.game_over:
    st.session_state.last_refresh = time.time()
    st.rerun()  # 替换为稳定版st.rerun()

# ---------------------- 6. 游戏状态提示 ----------------------
st.divider()
if st.session_state.game_over:
    if st.session_state.winner == "平局":
        st.success(f"🟰 房间 {room_id} - 平局！")
    else:
        st.success(f"🏆 房间 {room_id} - 玩家 {st.session_state.winner} 获胜！")
else:
    st.info(f"📌 房间 {room_id} - 当前回合：仅玩家 {st.session_state.current_player} 可落子")

# ---------------------- 7. 3x3棋盘（权限控制） ----------------------
st.subheader("游戏棋盘")
for row in range(3):
    cols = st.columns(3)
    for col in range(3):
        idx = row * 3 + col
        with cols[col]:
            btn_text = st.session_state.board[idx] if st.session_state.board[idx] != "" else "　"
            is_disabled = st.session_state.game_over or st.session_state.board[idx] != ""
            btn_clicked = st.button(
                btn_text,
                key=f"{room_id}_{idx}",
                disabled=is_disabled,
                use_container_width=True,
                type="primary" if st.session_state.board[idx] == "X" else "secondary"
            )
            if btn_clicked:
                # 落子并切换玩家
                st.session_state.board[idx] = st.session_state.current_player
                st.session_state.winner = check_winner(st.session_state.board)
                if st.session_state.winner is not None:
                    st.session_state.game_over = True
                else:
                    st.session_state.current_player = "O" if st.session_state.current_player == "X" else "X"
                # 同步到云端
                save_game_state({
                    "object_id": st.session_state.object_id,
                    "room_id": room_id,
                    "board": st.session_state.board,
                    "current_player": st.session_state.current_player,
                    "game_over": st.session_state.game_over,
                    "winner": st.session_state.winner
                })
                st.rerun()

# ---------------------- 8. 重置游戏 ----------------------
def reset_game():
    reset_data = {
        "object_id": st.session_state.object_id,
        "room_id": room_id,
        "board": [""] * 9,
        "current_player": "X",
        "game_over": False,
        "winner": None
    }
    save_game_state(reset_data)
    st.session_state.board = [""] * 9
    st.session_state.current_player = "X"
    st.session_state.game_over = False
    st.session_state.winner = None
    st.rerun()

st.divider()
st.button("🔄 重新开始本局", on_click=reset_game, use_container_width=True)
st.caption(f"💡 联机说明：输入相同房间ID，X/O轮流落子，自动同步")