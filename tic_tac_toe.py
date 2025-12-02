import streamlit as st
import leancloud  # 确保已安装：pip install leancloud

# 1. 初始化LeanCloud（替换成你的App ID和App Key）
leancloud.init(
    app_id="hiwS1jgaGdLqJhk2UtEwHGdK-gzGzoHsz",  # 粘贴刚才复制的App ID
    app_key="bENg8Yr0UlGdt7NJB70i2VOW"  # 粘贴刚才复制的App Key
)
# 国内应用需要指定服务器地址（默认是国内地址，可加此行确保正确）
leancloud.use_region("CN")

# 2. 定义数据表（必须和你创建的Class名称一致：GameState）
GameState = leancloud.Object.extend("GameState")

# 3. 从LeanCloud读取游戏状态（代码不变，直接用）
def load_game_state():
    query = GameState.query
    results = query.find()  # 查找表中所有数据
    if not results:  # 如果表是空的，初始化一个新游戏
        new_game = GameState()
        new_game.set("board", [""]*9)  # 空棋盘
        new_game.set("current_player", "X")  # 玩家X先行
        new_game.set("game_over", False)
        new_game.set("winner", None)
        new_game.save()  # 保存到LeanCloud
        return {
            "board": [""]*9,
            "current_player": "X",
            "game_over": False,
            "winner": None
        }
    else:  # 如果表中有数据，读取最新状态
        game = results[0]
        return {
            "board": game.get("board"),
            "current_player": game.get("current_player"),
            "game_over": game.get("game_over"),
            "winner": game.get("winner")
        }

# 4. 保存游戏状态到LeanCloud（代码不变，直接用）
def save_game_state(state):
    query = GameState.query
    results = query.find()
    if results:  # 更新已有数据
        game = results[0]
    else:  # 如果没有数据，创建新记录
        game = GameState()
    # 更新状态（board、玩家、游戏是否结束等）
    game.set("board", state["board"])
    game.set("current_player", state["current_player"])
    game.set("game_over", state["game_over"])
    game.set("winner", state["winner"])
    game.save()  # 保存到LeanCloud

# 5. 加载游戏状态（替换原来的本地初始化代码）
game_state = load_game_state()
st.session_state.board = game_state["board"]
st.session_state.current_player = game_state["current_player"]
st.session_state.game_over = game_state["game_over"]
st.session_state.winner = game_state["winner"]

# 6. 棋盘布局代码（用之前修改的3x3适配手机的代码，确保按钮点击后保存状态）
# （这部分代码不变，只需确保按钮点击后调用save_game_state）
st.subheader("游戏棋盘")
for row in range(3):
    cols_in_row = st.columns(3)
    for col in range(3):
        grid_index = row * 3 + col
        with cols_in_row[col]:
            btn_text = st.session_state.board[grid_index] if st.session_state.board[grid_index] != "" else "　"
            btn_clicked = st.button(
                btn_text,
                key=grid_index,
                disabled=st.session_state.game_over or st.session_state.board[grid_index] != "",
                use_container_width=True,
                type="primary" if st.session_state.board[grid_index] == "X" else "secondary"
            )
            if btn_clicked:
                st.session_state.board[grid_index] = st.session_state.current_player
                # 检查胜负（原来的check_winner函数不变）
                st.session_state.winner = check_winner()
                if st.session_state.winner is not None:
                    st.session_state.game_over = True
                else:
                    st.session_state.current_player = "O" if st.session_state.current_player == "X" else "X"
                # 关键：保存状态到LeanCloud
                save_game_state({
                    "board": st.session_state.board,
                    "current_player": st.session_state.current_player,
                    "game_over": st.session_state.game_over,
                    "winner": st.session_state.winner
                })
                st.rerun()

# 7. 重置游戏按钮（确保重置后同步到LeanCloud）
def reset_game():
    st.session_state.board = [""]*9
    st.session_state.current_player = "X"
    st.session_state.game_over = False
    st.session_state.winner = None
    # 同步重置LeanCloud数据
    save_game_state({
        "board": [""]*9,
        "current_player": "X",
        "game_over": False,
        "winner": None
    })

st.button("🔄 重新开始游戏", on_click=reset_game, use_container_width=True)