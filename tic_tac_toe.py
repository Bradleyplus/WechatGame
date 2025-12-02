import streamlit as st
import requests
import uuid
import time

# ---------------------- 页面样式与配置 ----------------------
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
</style>
""", unsafe_allow_html=True)

# ---------------------- 核心配置 ----------------------
APP_ID = "hiwS1jgaGdLqJhk2UtEwHGdK-gzGzoHsz"
APP_KEY = "bENg8Yr0UlGdt7NJB70i2VOW"
BASE_API_URL = "https://api.leancloud.cn/1.1/classes/GameState"
HEADERS = {
    "X-LC-Id": APP_ID,
    "X-LC-Key": APP_KEY,
    "Content-Type": "application/json"
}


# ---------------------- 工具函数 ----------------------
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


def get_device_id():
    if "device_id" not in st.session_state:
        st.session_state.device_id = str(uuid.uuid4())
    return st.session_state.device_id


# ---------------------- 房间强制清理与校验 ----------------------
def force_clean_room(room_id):
    """强制清理指定房间的所有记录（解决残留占用）"""
    try:
        # 查找房间
        params = {"where": f'{{"room_id":"{room_id}"}}', "limit": 1}
        res = requests.get(BASE_API_URL, headers=HEADERS, params=params, timeout=10)
        res.raise_for_status()
        data = res.json()
        if data.get("results"):
            # 存在则删除
            object_id = data["results"][0]["objectId"]
            requests.delete(f"{BASE_API_URL}/{object_id}", headers=HEADERS, timeout=10)
            st.success(f"房间 {room_id} 已强制清理！")
            time.sleep(1)  # 等待删除生效
            return True
        else:
            st.info(f"房间 {room_id} 不存在，无需清理")
            return True
    except Exception as e:
        st.error(f"清理失败：{str(e)}")
        return False


def validate_room_state(room_data):
    """校验房间状态是否有效（过滤无效占用）"""
    if not room_data:
        return None
    # 校验玩家数量是否合理（0-2）
    player_count = room_data.get("player_count", 0)
    if player_count < 0 or player_count > 2:
        return None  # 无效状态，视为房间不存在
    # 校验玩家列表是否有效
    players = room_data.get("players", {})
    if len(players) != player_count:
        return None  # 玩家数量与列表不匹配，视为无效
    return room_data


# ---------------------- 房间操作 ----------------------
def load_room(room_id):
    """加载并校验房间状态"""
    try:
        params = {"where": f'{{"room_id":"{room_id}"}}', "limit": 1}
        res = requests.get(BASE_API_URL, headers=HEADERS, params=params, timeout=10)
        res.raise_for_status()
        data = res.json()
        room_data = data["results"][0] if data.get("results") else None
        return validate_room_state(room_data)  # 仅返回有效状态
    except Exception as e:
        st.error(f"加载房间失败：{str(e)}")
        return None


def create_room(room_id):
    """创建新房间"""
    device_id = get_device_id()
    new_room = {
        "room_id": room_id,
        "board": ["", "", "", "", "", "", "", "", ""],
        "current_player": "X",
        "game_over": False,
        "winner": None,
        "player_count": 1,
        "players": {device_id: "X"}
    }
    res = requests.post(BASE_API_URL, headers=HEADERS, json=new_room, timeout=10)
    res.raise_for_status()
    new_data = res.json()
    return {**new_room, "objectId": new_data["objectId"]}


def enter_room(room_id):
    """进入房间：优先清理无效状态，再创建/加入"""
    device_id = get_device_id()
    room_data = load_room(room_id)

    # 情况1：房间无效或不存在，直接创建新房间
    if not room_data:
        return create_room(room_id)

    # 情况2：房间有效，检查是否可加入
    current_count = room_data["player_count"]
    current_players = room_data["players"]

    # 已在房间中，直接返回
    if device_id in current_players:
        return room_data

    # 未满2人，加入为O
    if current_count < 2:
        updated_players = current_players.copy()
        updated_players[device_id] = "O"
        updated_data = {**room_data, "player_count": current_count + 1, "players": updated_players}
        requests.put(f"{BASE_API_URL}/{room_data['objectId']}", headers=HEADERS, json=updated_data, timeout=10)
        return updated_data

    # 房间已满
    return None


def exit_room(room_id):
    """退出房间：最后一人退出时强制删除"""
    device_id = get_device_id()
    room_data = load_room(room_id)
    if not room_data:
        return

    current_players = room_data["players"].copy()
    current_count = room_data["player_count"]

    # 不在房间中，无需处理
    if device_id not in current_players:
        return

    # 移除当前玩家
    del current_players[device_id]
    new_count = current_count - 1

    # 最后一人退出：强制删除房间
    if new_count == 0:
        force_clean_room(room_id)
    else:
        # 更新房间状态
        updated_data = {**room_data, "player_count": new_count, "players": current_players}
        requests.put(f"{BASE_API_URL}/{room_data['objectId']}", headers=HEADERS, json=updated_data, timeout=10)


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

# 紧急清理按钮（核心解决占用问题）
if st.button("⚠️ 强制清理房间（解决占用）", use_container_width=True, type="secondary"):
    force_clean_room(room_id)
    st.rerun()

# 操作按钮
col1, col2 = st.columns(2)
with col1:
    if st.button("🔄 刷新状态", use_container_width=True):
        if st.session_state.entered_room:
            room_data = load_room(room_id)
            if not room_data:
                st.session_state.entered_room = False
                st.error("房间已解散，请重新进入")
            else:
                st.session_state.board = room_data["board"]
                st.session_state.current_player = room_data["current_player"]
                st.session_state.game_over = room_data["game_over"]
                st.session_state.winner = room_data["winner"]
                st.session_state.player_count = room_data["player_count"]
                st.session_state.players = room_data["players"]
                st.session_state.my_role = room_data["players"].get(get_device_id())
                st.success("状态已刷新")
        else:
            st.info("请先进入房间")

with col2:
    if st.button("🚪 退出房间", use_container_width=True) and st.session_state.entered_room:
        exit_room(room_id)
        st.session_state.entered_room = False
        st.session_state.my_role = None
        st.success("已退出房间")
        st.rerun()

# 进入房间按钮
if not st.session_state.entered_room:
    if st.button("📥 进入房间", use_container_width=True, type="primary"):
        room_data = enter_room(room_id)
        if room_data:
            st.session_state.entered_room = True
            st.session_state.object_id = room_data["objectId"]
            st.session_state.board = room_data["board"]
            st.session_state.current_player = room_data["current_player"]
            st.session_state.game_over = room_data["game_over"]
            st.session_state.winner = room_data["winner"]
            st.session_state.player_count = room_data["player_count"]
            st.session_state.players = room_data["players"]
            st.session_state.my_role = room_data["players"][get_device_id()]
            st.success(f"进入房间 {room_id}，角色：{st.session_state.my_role}")
            st.rerun()
        else:
            st.error("房间已满！可尝试先点击「强制清理房间」")

# 游戏棋盘（已进入房间时）
if st.session_state.entered_room and st.session_state.my_role:
    st.divider()
    st.info(
        f"房间 {room_id}（{st.session_state.player_count}/2人）| 你的角色：{st.session_state.my_role} | 当前回合：{st.session_state.current_player}")

    if st.session_state.game_over:
        if st.session_state.winner == "平局":
            st.success("🟰 平局！")
        else:
            st.success(f"🏆 {st.session_state.winner} 获胜！")

    # 棋盘
    st.subheader("游戏棋盘")
    with st.container():
        st.markdown('<div class="board-container">', unsafe_allow_html=True)
        rows = [st.columns(3, gap="small") for _ in range(3)]
        grid = [col for row in rows for col in row]

        for i in range(9):
            with grid[i]:
                text = st.session_state.board[i] if st.session_state.board[i] else " "
                disabled = (
                        st.session_state.game_over
                        or st.session_state.board[i]
                        or st.session_state.my_role != st.session_state.current_player
                )
                if st.button(
                        text,
                        key=f"cell_{i}",
                        disabled=disabled,
                        use_container_width=True,
                        type="primary" if text == "X" else "secondary"
                ):
                    st.session_state.board[i] = st.session_state.my_role
                    winner = check_winner(st.session_state.board)
                    if winner:
                        st.session_state.game_over = True
                        st.session_state.winner = winner
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
                        st.warning(f"同步失败：{str(e)}")
                    st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    # 重置游戏
    if st.button("🔄 重新开始", use_container_width=True):
        st.session_state.board = ["", "", "", "", "", "", "", "", ""]
        st.session_state.current_player = "X"
        st.session_state.game_over = False
        st.session_state.winner = None
        try:
            update_data = {
                "board": st.session_state.board,
                "current_player": "X",
                "game_over": False,
                "winner": None
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

st.caption("""
💡 解决房间占用：
1. 若提示"房间已满"，先点击「强制清理房间」
2. 清理后再点击「进入房间」即可创建新房间
3. 退出时会自动删除房间记录，避免占用
""")