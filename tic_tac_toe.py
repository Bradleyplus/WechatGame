import streamlit as st
import requests
import uuid

# ---------------------- 页面样式优化 ----------------------
st.set_page_config(
    page_title="双人井字棋",
    layout="centered",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    .board-container {
        width: 100% !important;
        max-width: 210px !important;
        margin: 0 auto !important;
    }
    .stButton > button {
        width: 100% !important;
        height: 60px !important;
        font-size: 1.5rem !important;
        padding: 0 !important;
        margin: 1px !important;
    }
    @media (max-width: 400px) {
        .board-container {
            max-width: 180px !important;
        }
        .stButton > button {
            height: 50px !important;
            font-size: 1.2rem !important;
        }
    }
    .stColumns {
        flex-wrap: nowrap !important;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------- LeanCloud配置 ----------------------
APP_ID = "hiwS1jgaGdLqJhk2UtEwHGdK-gzGzoHsz"
APP_KEY = "bENg8Yr0UlGdt7NJB70i2VOW"
BASE_API_URL = "https://api.leancloud.cn/1.1/classes/GameState"
HEADERS = {
    "X-LC-Id": APP_ID,
    "X-LC-Key": APP_KEY,
    "Content-Type": "application/json"
}


# ---------------------- 胜负判断函数 ----------------------
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


# ---------------------- 读取/删除房间状态 ----------------------
def load_game_state(room_id):
    try:
        params = {"where": f'{{"room_id":"{room_id}"}}', "limit": 1}
        response = requests.get(BASE_API_URL, headers=HEADERS, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data["results"][0] if data.get("results") else None
    except Exception as e:
        st.error(f"加载房间失败：{str(e)}")
        return None


def delete_room_state(object_id):
    """强制删除房间记录"""
    try:
        requests.delete(f"{BASE_API_URL}/{object_id}", headers=HEADERS, timeout=10)
    except Exception as e:
        st.warning(f"清除房间失败：{str(e)}")


# ---------------------- 房间管理（修复核心问题） ----------------------
def get_device_id():
    """确保设备ID唯一且存在"""
    if "device_id" not in st.session_state:
        st.session_state.device_id = str(uuid.uuid4())
    return st.session_state.device_id


def enter_room(room_id):
    """进入房间：确保新设备正确添加到玩家列表"""
    device_id = get_device_id()
    game_data = load_game_state(room_id)

    # 情况1：房间不存在，创建新房间（第一个玩家为X）
    if not game_data:
        new_room = {
            "room_id": room_id,
            "board": ["", "", "", "", "", "", "", "", ""],
            "current_player": "X",
            "game_over": False,
            "winner": None,
            "player_count": 1,
            "players": {device_id: "X"}  # 强制添加当前设备
        }
        res = requests.post(BASE_API_URL, headers=HEADERS, json=new_room, timeout=10)
        res.raise_for_status()
        new_data = res.json()
        return {**new_room, "objectId": new_data["objectId"]}

    # 情况2：房间存在，检查是否可加入
    current_players = game_data.get("players", {})
    current_count = game_data.get("player_count", 0)

    # 若当前设备已在房间中，直接返回
    if device_id in current_players:
        return game_data

    # 若房间未满（<2人），添加为第二个玩家（O）
    if current_count < 2:
        updated_players = current_players.copy()
        updated_players[device_id] = "O"  # 强制添加当前设备为O
        updated_data = {
            **game_data,
            "player_count": current_count + 1,
            "players": updated_players
        }
        requests.put(f"{BASE_API_URL}/{game_data['objectId']}", headers=HEADERS, json=updated_data, timeout=10)
        return updated_data

    # 房间已满
    return None


def exit_room(room_id):
    """退出房间：最后一人退出时强制删除房间"""
    device_id = get_device_id()
    game_data = load_game_state(room_id)
    if not game_data:
        return

    current_players = game_data.get("players", {})
    current_count = game_data.get("player_count", 0)

    # 若当前设备不在房间中，无需处理
    if device_id not in current_players:
        return

    # 移除当前设备
    updated_players = current_players.copy()
    del updated_players[device_id]
    new_count = current_count - 1

    # 最后一人退出：强制删除房间
    if new_count == 0:
        delete_room_state(game_data["objectId"])
    else:
        # 还有玩家：更新状态
        updated_data = {**game_data, "player_count": new_count, "players": updated_players}
        requests.put(f"{BASE_API_URL}/{game_data['objectId']}", headers=HEADERS, json=updated_data, timeout=10)


# ---------------------- 页面逻辑 ----------------------
st.title("🎮 双人井字棋（联机版）")

# 房间选择
room_id = st.selectbox(
    "🔑 选择游戏房间",
    options=["8888", "6666"],
    index=0,
    key="room_selector"
)

# 初始化会话状态
for key in ["entered_room", "my_role", "object_id", "board", "current_player", "game_over", "winner", "player_count",
            "players"]:
    if key not in st.session_state:
        st.session_state[key] = False if key == "entered_room" else None

# 操作按钮
col_refresh, col_exit = st.columns(2)
with col_refresh:
    if st.button("🔄 刷新状态", use_container_width=True):
        if st.session_state.entered_room:
            game_data = load_game_state(room_id)
            if not game_data:  # 房间已被删除
                st.session_state.entered_room = False
                st.error("房间已解散，请重新进入")
            else:
                # 安全更新状态
                st.session_state.board = game_data.get("board", ["", "", "", "", "", "", "", "", ""])
                st.session_state.current_player = game_data.get("current_player", "X")
                st.session_state.game_over = game_data.get("game_over", False)
                st.session_state.winner = game_data.get("winner")
                st.session_state.player_count = game_data.get("player_count", 0)
                st.session_state.players = game_data.get("players", {})
                st.session_state.my_role = st.session_state.players.get(get_device_id())
                st.success("状态已刷新")
        else:
            st.info("请先进入房间")

with col_exit:
    if st.button("🚪 退出房间", use_container_width=True) and st.session_state.entered_room:
        exit_room(room_id)
        # 重置所有状态
        st.session_state.entered_room = False
        st.session_state.my_role = None
        st.session_state.object_id = None
        st.session_state.board = []
        st.success("已退出房间，记录已清除")
        st.rerun()

# 进入房间按钮
if not st.session_state.entered_room:
    if st.button("📥 进入房间", use_container_width=True):
        room_data = enter_room(room_id)
        if room_data:
            st.session_state.entered_room = True
            st.session_state.object_id = room_data["objectId"]
            st.session_state.board = room_data.get("board", ["", "", "", "", "", "", "", "", ""])
            st.session_state.current_player = room_data.get("current_player", "X")
            st.session_state.game_over = room_data.get("game_over", False)
            st.session_state.winner = room_data.get("winner")
            st.session_state.player_count = room_data.get("player_count", 0)
            st.session_state.players = room_data.get("players", {})
            # 安全获取角色（修复KeyError核心）
            st.session_state.my_role = st.session_state.players.get(get_device_id(), "未知")
            st.success(f"已进入房间 {room_id}，您的角色：{st.session_state.my_role}")
            st.rerun()
        else:
            st.error("房间已满或创建失败，请稍后再试")

# 已进入房间：显示棋盘
if st.session_state.entered_room and st.session_state.my_role != "未知":
    st.divider()
    st.info(f"""
    📌 房间 {room_id}（{st.session_state.player_count}/2人）
    您的角色：{st.session_state.my_role} | 当前回合：{st.session_state.current_player}
    """)

    if st.session_state.game_over:
        if st.session_state.winner == "平局":
            st.success("🟰 游戏结束：平局！")
        else:
            st.success(f"🏆 游戏结束：玩家 {st.session_state.winner} 获胜！")

    # 九宫格棋盘
    st.subheader("游戏棋盘")
    with st.container():
        st.markdown('<div class="board-container">', unsafe_allow_html=True)

        row1 = st.columns(3, gap="small")
        row2 = st.columns(3, gap="small")
        row3 = st.columns(3, gap="small")
        grid_cols = [row1[0], row1[1], row1[2], row2[0], row2[1], row2[2], row3[0], row3[1], row3[2]]

        for grid_idx in range(9):
            with grid_cols[grid_idx]:
                btn_text = st.session_state.board[grid_idx] if st.session_state.board[grid_idx] != "" else " "
                is_disabled = (
                        st.session_state.game_over
                        or st.session_state.board[grid_idx] != ""
                        or st.session_state.my_role != st.session_state.current_player
                )

                if st.button(
                        btn_text,
                        key=f"btn_{room_id}_{grid_idx}",
                        disabled=is_disabled,
                        use_container_width=True,
                        type="primary" if st.session_state.board[grid_idx] == "X" else "secondary"
                ):
                    # 落子逻辑
                    st.session_state.board[grid_idx] = st.session_state.my_role
                    st.session_state.winner = check_winner(st.session_state.board)
                    if st.session_state.winner:
                        st.session_state.game_over = True
                        st.session_state.current_player = None
                    else:
                        st.session_state.current_player = "O" if st.session_state.current_player == "X" else "X"

                    # 保存状态
                    try:
                        update_data = {
                            "board": st.session_state.board,
                            "current_player": st.session_state.current_player,
                            "game_over": st.session_state.game_over,
                            "winner": st.session_state.winner,
                            "player_count": st.session_state.player_count,
                            "players": st.session_state.players
                        }
                        requests.put(
                            f"{BASE_API_URL}/{st.session_state.object_id}",
                            headers=HEADERS,
                            json=update_data,
                            timeout=10
                        )
                        st.success("落子成功！请对方刷新")
                    except Exception as e:
                        st.warning(f"落子同步失败：{str(e)}")
                    st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)

    # 重置游戏
    if st.button("🔄 重新开始本局", use_container_width=True):
        reset_board = ["", "", "", "", "", "", "", "", ""]
        st.session_state.board = reset_board
        st.session_state.current_player = "X"
        st.session_state.game_over = False
        st.session_state.winner = None
        try:
            update_data = {
                "board": reset_board,
                "current_player": "X",
                "game_over": False,
                "winner": None,
                "player_count": st.session_state.player_count,
                "players": st.session_state.players
            }
            requests.put(
                f"{BASE_API_URL}/{st.session_state.object_id}",
                headers=HEADERS,
                json=update_data,
                timeout=10
            )
            st.success("游戏已重置")
        except Exception as e:
            st.warning(f"重置失败：{str(e)}")
        st.rerun()

# 操作说明
st.caption("""
💡 注意：
1. 退出房间后，若无人剩余，房间记录会自动清除
2. 若提示"房间已解散"，请重新进入即可创建新房间
3. 角色固定为X（先进入）和O（后进入），不可更改
""")