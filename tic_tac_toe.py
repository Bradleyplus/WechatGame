import streamlit as st
import requests
import time

# ---------------------- 1. LeanCloud配置（替换为你的App ID/Key） ----------------------
APP_ID = "hiwS1jgaGdLqJhk2UtEwHGdK-gzGzoHsz"  # 必须替换！
APP_KEY = "bENg8Yr0UlGdt7NJB70i2VOW"  # 必须替换！
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


# ---------------------- 3. 按房间ID读取游戏状态（联机核心） ----------------------
def load_game_state(room_id):
    try:
        # 按房间ID查询，只查该房间的游戏状态
        params = {"where": f'{{"room_id":"{room_id}"}}'}
        response = requests.get(BASE_API_URL, headers=HEADERS, params=params, timeout=10)
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
            # 新房间：初始化游戏状态并保存
            init_game = {
                "room_id": room_id,
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
                "winner": None,
                "room_id": room_id
            }
    except Exception as e:
        st.error(f"连接服务器失败：{str(e)}")
        # 本地降级（仅临时使用）
        return {
            "object_id": "local",
            "board": [""] * 9,
            "current_player": "X",
            "game_over": False,
            "winner": None,
            "room_id": room_id
        }


# ---------------------- 4. 保存游戏状态（按房间ID更新） ----------------------
def save_game_state(state):
    if state["object_id"] == "local":
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
        requests.put(update_url, json=update_data, headers=HEADERS, timeout=10)
    except Exception as e:
        st.warning(f"同步失败：{str(e)}")


# ---------------------- 5. 初始化页面（自动刷新+房间ID） ----------------------
# 开启自动刷新（每2秒刷新一次，实现实时同步）
st.autorefresh(interval=2000, key="auto_refresh")

st.title("🎮 双人井字棋（联机版）")

# 房间ID输入框（核心：相同ID进入同一局）
room_id = st.text_input("🔑 输入房间ID（和好友填相同ID即可联机）", value="default", max_chars=20)
if not room_id:
    room_id = "default"

# 初始化游戏状态（按房间ID）
if "room_id" not in st.session_state or st.session_state.room_id != room_id:
    # 切换房间时重置状态
    game_state = load_game_state(room_id)
    st.session_state.object_id = game_state["object_id"]
    st.session_state.board = game_state["board"]
    st.session_state.current_player = game_state["current_player"]
    st.session_state.game_over = game_state["game_over"]
    st.session_state.winner = game_state["winner"]
    st.session_state.room_id = room_id
else:
    # 同一房间：拉取最新状态（实现实时同步）
    game_state = load_game_state(room_id)
    st.session_state.board = game_state["board"]
    st.session_state.current_player = game_state["current_player"]
    st.session_state.game_over = game_state["game_over"]
    st.session_state.winner = game_state["winner"]

# ---------------------- 6. 游戏状态提示 ----------------------
st.divider()
if st.session_state.game_over:
    if st.session_state.winner == "平局":
        st.success(f"🟰 房间 {room_id} - 游戏结束：平局！")
    else:
        st.success(f"🏆 房间 {room_id} - 游戏结束：玩家 {st.session_state.winner} 获胜！")
else:
    st.info(f"📌 房间 {room_id} - 当前回合：玩家 {st.session_state.current_player}（自动同步中）")

# ---------------------- 7. 3x3联机棋盘（微信适配） ----------------------
st.subheader("游戏棋盘")
for row in range(3):
    cols = st.columns(3)
    for col in range(3):
        idx = row * 3 + col
        with cols[col]:
            btn_text = st.session_state.board[idx] if st.session_state.board[idx] != "" else "　"
            btn_clicked = st.button(
                btn_text,
                key=f"{room_id}_{idx}",  # 加房间ID避免不同房间按钮冲突
                disabled=st.session_state.game_over or st.session_state.board[idx] != "",
                use_container_width=True,
                type="primary" if st.session_state.board[idx] == "X" else "secondary"
            )
            if btn_clicked:
                # 落子并更新状态
                st.session_state.board[idx] = st.session_state.current_player
                st.session_state.winner = check_winner(st.session_state.board)
                if st.session_state.winner is not None:
                    st.session_state.game_over = True
                else:
                    st.session_state.current_player = "O" if st.session_state.current_player == "X" else "X"
                # 保存状态到服务器（同步给好友）
                save_game_state({
                    "object_id": st.session_state.object_id,
                    "room_id": room_id,
                    "board": st.session_state.board,
                    "current_player": st.session_state.current_player,
                    "game_over": st.session_state.game_over,
                    "winner": st.session_state.winner
                })
                # 强制刷新页面，立即显示最新状态
                st.rerun()


# ---------------------- 8. 重置游戏按钮 ----------------------
def reset_game():
    st.session_state.board = [""] * 9
    st.session_state.current_player = "X"
    st.session_state.game_over = False
    st.session_state.winner = None
    # 同步重置服务器状态
    save_game_state({
        "object_id": st.session_state.object_id,
        "room_id": room_id,
        "board": [""] * 9,
        "current_player": "X",
        "game_over": False,
        "winner": None
    })


st.divider()
st.button("🔄 重新开始本局", on_click=reset_game, use_container_width=True)
st.caption(f"💡 联机说明：和好友输入相同房间ID，落子后自动同步（无需刷新）\n当前房间：{room_id}")