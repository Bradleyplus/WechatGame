import streamlit as st

# 初始化游戏状态（Streamlit会话存储，刷新不丢失）
if "board" not in st.session_state:
    st.session_state.board = [""] * 9  # 9个格子的棋盘
if "current_player" not in st.session_state:
    st.session_state.current_player = "X"  # 玩家1：X，玩家2：O
if "game_over" not in st.session_state:
    st.session_state.game_over = False
if "winner" not in st.session_state:
    st.session_state.winner = None

# 游戏核心逻辑：检查胜负
def check_winner():
    # 获胜的8种组合（横、竖、斜）
    win_combinations = [
        (0,1,2), (3,4,5), (6,7,8),  # 横
        (0,3,6), (1,4,7), (2,5,8),  # 竖
        (0,4,8), (2,4,6)             # 斜
    ]
    for combo in win_combinations:
        a, b, c = combo
        if st.session_state.board[a] == st.session_state.board[b] == st.session_state.board[c] != "":
            return st.session_state.board[a]  # 返回获胜方（X/O）
    # 检查平局（棋盘满了但没赢家）
    if "" not in st.session_state.board:
        return "平局"
    return None

# 重置游戏
def reset_game():
    st.session_state.board = [""] * 9
    st.session_state.current_player = "X"
    st.session_state.game_over = False
    st.session_state.winner = None

# 页面布局（适配手机/微信）
st.set_page_config(page_title="双人井字棋", page_icon="🎮", layout="centered")
st.title("🎮 双人井字棋（微信版）")
st.caption("玩家1（X）先出，玩家2（O）后出，连成一线即获胜！")

# 显示当前玩家
if not st.session_state.game_over:
    st.info(f"当前回合：玩家{1 if st.session_state.current_player == 'X' else 2}（{st.session_state.current_player}）")
else:
    if st.session_state.winner == "平局":
        st.success("😝 游戏平局！")
    else:
        st.success(f"🎉 玩家{1 if st.session_state.winner == 'X' else 2}（{st.session_state.winner}）获胜！")

# 绘制棋盘（3x3网格按钮）
cols = st.columns(3)  # 3列布局
for i in range(9):
    with cols[i % 3]:
        # 按钮显示X/O或空，点击后落子
        btn = st.button(
            st.session_state.board[i] if st.session_state.board[i] != "" else "　",
            key=i,
            disabled=st.session_state.game_over or st.session_state.board[i] != "",
            use_container_width=True,  # 按钮占满列宽（适配手机）
            type="primary" if st.session_state.board[i] == "X" else "secondary"  # X/O区分颜色
        )
        if btn:
            # 落子并切换玩家
            st.session_state.board[i] = st.session_state.current_player
            # 检查胜负
            st.session_state.winner = check_winner()
            if st.session_state.winner is not None:
                st.session_state.game_over = True
            else:
                # 切换玩家
                st.session_state.current_player = "O" if st.session_state.current_player == "X" else "X"
            # 刷新页面（更新状态）
            st.rerun()

# 重置游戏按钮
st.divider()
st.button("🔄 重新开始游戏", on_click=reset_game, use_container_width=True)