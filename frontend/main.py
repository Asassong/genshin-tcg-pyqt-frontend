# from gcg import Ui_GCG
import sys
from PyQt6.QtWidgets import QMainWindow, QApplication, QLabel, QFrame, QVBoxLayout, QHBoxLayout, QGridLayout, QWidget, QPushButton
from PyQt6.QtNetwork import QUdpSocket, QHostAddress
from PyQt6.QtGui import QPixmap, QFont, QFontDatabase, QMouseEvent
from PyQt6.QtCore import QRect, pyqtSignal, Qt

class Gcg(QMainWindow):
    def __init__(self):
        super().__init__()
        self.resize(1280, 720)
        self.setWindowTitle("Genius Invokation TCG")
        # self.gui = Ui_GCG()
        # self.gui.setupUi(self)
        self.main_widget = QWidget(self)
        self.main_widget.resize(1280, 720)
        self.main_widget.setStyleSheet("border-image: url(./resources/background/background.png)")
        self.oppoDiceIcon = QLabel(self)
        self.oppoDiceIcon.setGeometry(QRect(14, 280, 50, 45))
        self.oppoDiceIcon.setPixmap(QPixmap("resources/images/oppo-dice-icon.png"))
        self.oppoDiceIcon.setScaledContents(True)
        self.opposCardNumIcon = QLabel(self)
        self.opposCardNumIcon.setGeometry(QRect(20, 185, 30, 40))
        self.opposCardNumIcon.setScaledContents(True)
        self.opposCardNumIcon.setPixmap(QPixmap("resources/images/card-num-icon.png"))
        self.playerDiceIcon = QLabel(self)
        self.playerDiceIcon.setGeometry(QRect(20, 380, 40, 40))
        self.playerDiceIcon.setPixmap(QPixmap("resources/images/own-dice-icon.png"))
        self.playerDiceIcon.setScaledContents(True)
        self.diceNum = QLabel(self)
        self.diceNum.setGeometry(QRect(29, 390, 20, 20))
        self.diceNum.setFont(QFont('HYWenHei-85W', 14))
        self.diceNum.setStyleSheet('color: white')
        self.diceNum.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # self.summonZone = QWidget(self)
        # self.summonZone.setGeometry(QRect(860, 380, 270, 200))
        self.end_round_button = QPushButton(self)
        self.end_round_button.setGeometry(QRect(10, 340, 75, 24))
        self.end_round_button.setText("结束回合")
        self.supportZone = SupportZone(self)
        self.supportZone.move(120, 380)
        self.play_card_button = QPushButton(self)
        self.play_card_button.setGeometry(QRect(510, 350, 75, 24))
        self.play_card_button.setText("打出卡牌")
        self.oppoCardNum = QLabel(self)
        self.oppoCardNum.setGeometry(QRect(25, 195, 20, 20))
        self.oppoCardNum.setFont(QFont('HYWenHei-85W', 14))
        self.oppoCardNum.setStyleSheet('color: white')
        self.oppoCardNum.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.change_char_button = QPushButton(self)
        self.change_char_button.setGeometry(QRect(1200, 580, 75, 24))
        self.change_char_button.setText("切换角色")
        self.oppoSupportZone =SupportZone(self)
        self.oppoSupportZone.move(120, 130)
        # self.oppoSummonZone = QWidget(self)
        # self.oppoSummonZone.setGeometry(QRect(860, 130, 270, 200))
        self.commit_button = QPushButton(self)
        self.commit_button.setGeometry(QRect(610, 350, 75, 24))
        self.commit_button.setText("确认")
        self.element_tuning_button = QPushButton(self)
        self.element_tuning_button.setGeometry(QRect(710, 350, 75, 24))
        self.element_tuning_button.setText("元素调和")
        self.oppoDiceNum = QLabel(self)
        self.oppoDiceNum.setGeometry(QRect(32, 292, 20, 20))
        self.oppoDiceNum.setFont(QFont('HYWenHei-85W', 14))
        self.oppoDiceNum.setStyleSheet('color: white')
        self.oppoDiceNum.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # # self.setStyleSheet("#main_widget{border-image: url(./resources/background/background.png)}")
        QFontDatabase.addApplicationFont("./resources/genshin.ttf") # 'HYWenHei-85W'
        self.element_tuning_button.hide()
        self.change_char_button.hide()
        self.commit_button.hide()
        self.play_card_button.hide()
        self.end_round_button.setEnabled(False)
        self._server_port = 4095
        self.card_zone = CardZone(self)
        self.skill_zone = SkillZone(self)
        self.card_zone.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.card_zone.installEventFilter(self)
        self._localhost = QHostAddress()
        self._localhost.setAddress("127.0.0.1")
        self._socket = QUdpSocket(self)
        self._socket.bind(self._localhost, self._server_port)
        self._socket.readyRead.connect(self.socket_recv)
        self.change_char_button.clicked.connect(self.choose_character)
        self.commit_button.clicked.connect(self.commit_operation)
        self.play_card_button.clicked.connect(self.play_card)
        self.element_tuning_button.clicked.connect(self.element_tuning)
        self.end_round_button.clicked.connect(self.round_end)
        self.redraw = Redraw(self, self.socket_send)
        # self.setStyleSheet("#redraw{background-color:rgba(0, 0, 0, 127)}")
        self.redraw.hide()
        self.reroll = Reroll(self, self.socket_send)
        self.reroll.hide()
        self.dice_zone = DiceZone(self)
        self.socket_send("connect request")
        self.characters: list[CharacterCard] = []
        self.oppose_char: list[CharacterCard] = []
        self.action_phase_start = False
        self.action_state = ""
        self.wait_change_state_obj = None

    def socket_recv(self):
        while self._socket.hasPendingDatagrams():
            datagram, _, _ = self._socket.readDatagram(self._socket.pendingDatagramSize())
            self.handle_recv(datagram)

    def socket_send(self, info: str):
        print("send", info)
        self._socket.writeDatagram(info.encode(), self._localhost, self._server_port)

    def handle_recv(self, datagram: bytes):
        data: str = datagram.decode()
        data: dict = eval(data)
        if data["message"] == "init_character":
            new_character = CharacterCard(self)
            position_map = {0: (440, 390), 1: (570, 390), 2: (700, 390)}
            position = position_map[data["position"]]
            new_character.move(*position)
            self.characters.append(new_character)
            char_name = data["character_name"]
            hp = data["hp"]
            energy = data["energy"]
            new_character.init(char_name, hp, energy)
            new_character.show()
        elif data["message"] == "init_oppo_character":
            new_character = CharacterCard(self)
            position_map = {0: (440, 90), 1: (570, 90), 2: (700, 90)}
            position = position_map[data["position"]]
            new_character.move(*position)
            self.oppose_char.append(new_character)
            char_name = data["character_name"]
            hp = data["hp"]
            energy = data["energy"]
            new_character.init(char_name, hp, energy)
            new_character.show()
        elif data["message"] == "change_energy":
            position = data["position"]
            obj = self.characters[position]
            energy = data["energy"]
            obj.change_energy(energy)
        elif data["message"] == "oppose_change_energy":
            position = data["position"]
            obj = self.oppose_char[position]
            energy = data["energy"]
            obj.change_energy(energy)
        elif data["message"] == "redraw":
            hands = data["hand"]
            self.redraw.show()
            self.redraw.raise_()
            picture_map = {1: self.redraw.card1, 2: self.redraw.card2, 3: self.redraw.card3,
                           4: self.redraw.card4, 5: self.redraw.card5}
            for index, hand in enumerate(hands):
                hand = hand.replace(" ", "")
                self.init_card_picture(picture_map[index+1], hand)
        elif data["message"] == "select_character":
            self.change_char_button.show()
        elif data["message"] == "player_change_active":
            self.change_active("player", data["change_from"], data["change_to"])
        elif data["message"] == "oppose_change_active":
            self.change_active("oppose", data["change_from"], data["change_to"])
        elif data["message"] == "add_card":
            self.card_zone.raise_()
            for card in data["cards"]:
                card = card.replace(" ", "")
                self.card_zone.add_card(card)
        elif data["message"] == "remove_card":
            self.card_zone.remove_card(data["card_index"])
        elif data["message"] == "reroll":
            self.reroll.show()
            self.reroll.raise_()
            self.reroll.show_dice(data["now_dice"])
        elif data["message"] == "oppose_card_num":
            self.oppoCardNum.setText(str(data["num"]))
        elif data["message"] == "show_dice_num":
            self.diceNum.setText(str(data["num"]))
        elif data["message"] == "show_oppose_dice_num":
            self.oppoDiceNum.setText(str(data["num"]))
        elif data["message"] == "add_dice":
            for dice in data["dices"]:
                self.dice_zone.add_dice(dice)
        elif data["message"] == "clear_dice":
            self.dice_zone.clear()
        elif data["message"] == "action_phase_start":
            self.end_round_button.setEnabled(True)
            self.action_phase_start = True
        elif data["message"] == "act_end":
            self.end_round_button.setEnabled(False)
            self.action_phase_start = False
        elif data["message"] == "highlight_dice":
            self.dice_zone.auto_highlight(data["dice_indexes"])
            self.action_state = "cost"
            self.commit_button.show()
            self.commit_button.setEnabled(True)
        elif data["message"] == "enable_commit":
            self.commit_button.setEnabled(True)
        elif data["message"] == "remove_dice":
            self.dice_zone.remove_dice(data["dices"])
        elif data["message"] == "init_skill":
            for skill_type in data["skills"]:
                self.skill_zone.add_widget(skill_type)
        elif data["message"] == "clear_skill":
            self.skill_zone.clear()
        elif data["message"] == "change_application":
            self.characters[data["position"]].change_application(data["application"])
        elif data["message"] == "oppose_change_application":
            self.oppose_char[data["position"]].change_application(data["application"])
        elif data["message"] == "change_hp":
            self.characters[data["position"]].change_hp(data["hp"])
        elif data["message"] == "oppose_change_hp":
            self.oppose_char[data["position"]].change_hp(data["hp"])
        elif data["message"] == "update_equip":
            self.characters[data["position"]].equip.clear()
            self.characters[data["position"]].change_equip(data["equip"])
        elif data["message"] == "oppose_update_equip":
            self.oppose_char[data["position"]].equip.clear()
            self.oppose_char[data["position"]].change_equip(data["equip"])
        elif data["message"] == "init_support":
            self.supportZone.add_widget(data["support_name"], data["count"])
        elif data["message"] == "init_oppose_support":
            self.oppoSupportZone.add_widget(data["support_name"], data["count"])
        elif data["message"] == "change_support_count":
            self.supportZone.change_support_count(data["support_index"], data["count"])
        elif data["message"] == "change_oppose_support_count":
            self.oppoSupportZone.change_support_count(data["support_index"], data["count"])
        elif data["message"] == "hide_oppose":
            self.oppoCardNum.hide()
            self.oppoDiceNum.hide()
            self.oppoSupportZone.hide()
            for oppo_char in self.oppose_char:
                oppo_char.hide()
        elif data["message"] == "show_oppose":
            self.oppoCardNum.show()
            self.oppoDiceNum.show()
            self.oppoSupportZone.show()
            for oppo_char in self.oppose_char:
                oppo_char.show()
        # else:
        print("recv", data)

    @staticmethod
    def init_card_picture(obj: QLabel, picture_name):
        picture = QPixmap("./resources/cards/%s.png" % picture_name)
        obj.setPixmap(picture)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self.action_phase_start:
            if self.action_state == "cost":
                self.socket_send(str({"message": "cancel"}))
            self.change_char_button.hide()

    def choose_character(self):
        for index, char in enumerate(self.characters):
            if char.is_chose():
                self.socket_send(
                    str({"message": "selected_character", "character": index}))
                self.change_char_button.hide()

    def change_active(self, whose, change_from, change_to):
        if whose == "player":
            if change_from is not None:
                need_move_frame = self.characters[change_from]
                need_move_frame.move(need_move_frame.x(), need_move_frame.y() + 20)
            need_move_frame = self.characters[change_to]
            need_move_frame.move(need_move_frame.x(), need_move_frame.y() - 20)
        else:
            if change_from is not None:
                need_move_frame = self.oppose_char[change_from]
                need_move_frame.move(need_move_frame.x(), need_move_frame.y() - 20)
            need_move_frame = self.oppose_char[change_to]
            need_move_frame.move(need_move_frame.x(), need_move_frame.y() + 20)

    def commit_operation(self):
        if self.action_state == "cost":
            choose = self.dice_zone.get_choose()
            self.action_state = ""
            self.socket_send(str({"message": "commit_cost", "cost": choose}))
            self.commit_button.hide()
        elif self.action_state == "skill":
            choose = self.skill_zone.get_choose()
            self.action_state = ""
            self.socket_send(str({"message": "use_skill", "skill_index": choose}))
            self.commit_button.hide()
            if isinstance(self.wait_change_state_obj, ClickableLabel):
                self.wait_change_state_obj.set_state(False)
                self.wait_change_state_obj = None

    def play_card(self):
        selected_card = self.card_zone.get_select()
        if selected_card is not None:
            self.socket_send(str({"message": "play_card", "card_index": selected_card}))
            self.play_card_button.hide()
            self.element_tuning_button.hide()

    def element_tuning(self):
        selected_card = self.card_zone.get_select()
        if selected_card is not None:
            self.socket_send(str({"message": "element_tuning", "card_index": selected_card}))
            self.play_card_button.hide()
            self.element_tuning_button.hide()

    def round_end(self):
        self.socket_send(str({"message": "round_end"}))

class CharacterCard(QFrame):
    def __init__(self, parent: Gcg):
        super().__init__(parent)
        self.game = parent
        self.resize(110, 200)
        self.frame = QFrame(self)
        self.frame.resize(110, 200)
        self.picture = ClickableLabel(self)
        self.picture.resize(110, 180)
        self.picture.move(0, 20)
        self.picture.setScaledContents(True)
        self.application = AutoResizeWidget(self, 20, "h", "element")
        hp_icon = QLabel(self)
        hp_icon.resize(30, 40)
        hp_icon.move(0, 20)
        hp_icon.setScaledContents(True)
        hp_pic = QPixmap("./resources/hp.png")
        hp_icon.setPixmap(hp_pic)
        self.hp = QLabel(self)
        self.hp.resize(20, 30)
        self.hp.move(5, 25)
        self.hp.setFont(QFont('HYWenHei-85W', 14))
        self.hp.setStyleSheet('color: white')
        self.hp.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.equip = AutoResizeWidget(self, 30, "v", "equip")
        self.equip.move(0, 60)
        self.energy = AutoResizeWidget(self, 30, "v", "energy")
        self.energy.move(80, 20)

    def init(self, character_name: str, hp: int, energy: tuple[int, int]):
        character_name = character_name.replace(" ", "")
        picture = QPixmap("./resources/characters/%s.png" % character_name)
        self.picture.setPixmap(picture)
        self.hp.setText(str(hp))
        self.change_energy(energy)

    def change_energy(self, energy: tuple[int, int]):
        self.energy.clear()
        now_energy, full = energy
        for _ in range(now_energy):
            self.energy.add_widget("fill")
        for _ in range(full - now_energy):
            self.energy.add_widget("empty")

    def change_hp(self, hp: int):
        self.hp.setText(str(hp))

    def is_chose(self) -> bool:
        if self.picture.get_state():
            self.picture.set_state(False)
            return True
        else:
            return False

    def change_equip(self, equipment: list):
        self.equip.clear()
        for equip in equipment:
            self.equip.add_widget(equip)

    def change_application(self, application: list):
        self.application.clear()
        for apply in application:
            self.application.add_widget(apply)

    @staticmethod
    def init_character_picture(obj: QLabel, picture_name):
        picture = QPixmap("./resources/characters/%s.png" % picture_name)
        obj.setPixmap(picture)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self.game.action_phase_start:
            obj = self.childAt(event.pos())
            if obj == self.picture:
                if self.pos().x() != 370:
                    self.game.change_char_button.show()
                else:
                    self.game.change_char_button.hide()
            else:
                event.ignore()

class Redraw(QWidget):
    def __init__(self, parent, func_send):
        super().__init__(parent)
        self.resize(1280, 720)
        self.setStyleSheet("QFrame{background-color:rgba(0, 0, 0, 127)}")
        frame = QFrame(self)
        frame.resize(1280, 720)
        self.commit = QPushButton(frame)
        self.commit.setGeometry(QRect(620, 560, 75, 24))
        self.commit.setText("commit")
        self.commit.setFont(QFont('HYWenHei-85W', 10))
        # self.commit.setStyleSheet('color: white')
        self.card1 = ClickableLabel(frame)
        self.card1.setGeometry(QRect(300, 240, 110, 180))
        self.card1.setText("")
        self.card1.setScaledContents(True)
        self.card2 = ClickableLabel(frame)
        self.card2.setGeometry(QRect(450, 240, 110, 180))
        self.card2.setText("")
        self.card2.setScaledContents(True)
        self.card3 = ClickableLabel(frame)
        self.card3.setGeometry(QRect(600, 240, 110, 180))
        self.card3.setText("")
        self.card3.setScaledContents(True)
        self.card4 = ClickableLabel(frame)
        self.card4.setGeometry(QRect(750, 240, 110, 180))
        self.card4.setText("")
        self.card4.setScaledContents(True)
        self.card5 = ClickableLabel(frame)
        self.card5.setGeometry(QRect(900, 240, 110, 180))
        self.card5.setText("")
        self.card5.setScaledContents(True)
        self.send = func_send
        self.commit.clicked.connect(self.hide_ui)

    def hide_ui(self):
        select = []
        for index, card in enumerate([self.card1, self.card2, self.card3, self.card4, self.card5]):
            if card.get_state():
                select.append(index)
        self.hide()
        select_message = {"message": "selected_card", "selected_card": select}
        self.send(str(select_message))

class ClickableLabel(QLabel):
    clicked = pyqtSignal()

    def __init__(self, parent):
        super().__init__(parent)
        self._state = False

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self._state = not self._state
        self.change_highlight()
        event.ignore()

    def get_state(self):
        return self._state

    def set_state(self, value: bool):
        self._state = value
        self.change_highlight()

    def change_highlight(self):
        if self._state:
            border = max(int(self.width() / 25), 1)
            self.setStyleSheet("border: %dpx solid rgb(255, 249, 205)" % border)
        else:
            self.setStyleSheet("border: 0px")

class CardZone(QWidget):
    def __init__(self, parent: Gcg):
        super().__init__(parent)
        self.resize(480, 200)
        self.move(370, 520)
        self.all_card: list[ClickableLabel] = []
        self.select_card = None
        self.game = parent

    @staticmethod
    def init_card_picture(obj: ClickableLabel, picture_name):
        picture = QPixmap("./resources/cards/%s.png" % picture_name)
        obj.setPixmap(picture)
    
    def add_card(self, card_name):
        new_card = ClickableLabel(self)
        new_card.resize(110, 180)
        new_card.setScaledContents(True)
        self.init_card_picture(new_card, card_name)
        new_card.move(48 * len(self.all_card), 80)
        new_card.show()
        self.all_card.append(new_card)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self.game.action_phase_start:
            obj = self.childAt(event.pos())
            if isinstance(obj, ClickableLabel):
                if obj.get_state():
                    if self.select_card is not None:
                        self.select_card.set_state(False)
                    self.select_card = obj
                    # cost_message = {"message": "check_card", "card_index": self.get_select()}
                    # self.game.socket_send(str(cost_message))
                    self.game.play_card_button.show()
                    # self.game.gui.play_card.setEnabled(False)
                    self.game.element_tuning_button.show()
                else:
                    self.select_card = None
                    self.game.play_card_button.hide()
                    self.game.element_tuning_button.hide()

    def get_select(self):
        if self.select_card is not None:
            return self.all_card.index(self.select_card)
        else:
            return None

    def remove_card(self, index):
        if self.select_card == self.all_card[index]:
            self.select_card = None  # 防止变量已删除再设state
        self.all_card[index].deleteLater()
        self.all_card.pop(index)
        for card in self.all_card[index:]:
            card.move(card.pos().x() - 48, 80)

class Reroll(QWidget):
    def __init__(self, parent, func_send):
        super().__init__(parent)
        self.resize(1280, 720)
        # self.setStyleSheet("QFrame{background-color:rgba(0, 0, 0, 127)}")
        self.dice_zone = AutoResizeWidget(self, 60, "h", "element")
        self.dice_zone.move(320, 300)
        self.commit = QPushButton(self)
        self.commit.setGeometry(QRect(620, 560, 75, 24))
        self.commit.setText("commit")
        self.commit.setFont(QFont('HYWenHei-85W', 10))
        self.commit.clicked.connect(self.commit_reroll)
        self.send_socket = func_send

    @staticmethod
    def init_dice_picture(obj: ClickableLabel, picture_name):
        picture = QPixmap("./resources/elements/%s.png" % picture_name)
        obj.setPixmap(picture)

    def show_dice(self, dices):
        self.dice_zone.clear()
        for element in dices:
            self.dice_zone.add_widget(element)

    def commit_reroll(self):
        choose = []
        for index, dice in enumerate(self.dice_zone.contain_widget):
            if dice.get_state():
                choose.append(index)
        reroll_message = {"message": "need_reroll", "need_reroll": choose}
        self.send_socket(str(reroll_message))
        self.hide()

class DiceZone(QWidget):
    def __init__(self, parent: Gcg):
        super().__init__(parent)
        self.resize(30, 480)
        self.move(1230, 50)
        self.frame = QFrame(self)
        self.frame.resize(40, 640)
        self.lo = QVBoxLayout()
        self.contain_dice: list[ClickableLabel] = []
        self.game = parent

    @staticmethod
    def init_dice_picture(obj: ClickableLabel, picture_name):
        picture = QPixmap("./resources/elements/%s.png" % picture_name)
        obj.setPixmap(picture)

    def add_dice(self, dice_name):
        dice_name = dice_name.lower()
        new_dice = ClickableLabel(self.frame)
        new_dice.setScaledContents(True)
        self.init_dice_picture(new_dice, dice_name)
        self.lo.addWidget(new_dice)
        self.contain_dice.append(new_dice)
        self.frame.resize(40, 40 * len(self.contain_dice))
        self.frame.setLayout(self.lo)

    def get_choose(self):
        choose = []
        for index, dice in enumerate(self.contain_dice):
            if dice.get_state():
                choose.append(index)
        return choose

    def remove_dice(self, indexes):
        indexes = sorted(indexes, reverse=True)
        for index in indexes:
            self.lo.itemAt(index).widget().deleteLater()
            self.contain_dice.pop(index)
        self.frame.resize(40, 40 * len(self.contain_dice))
        self.frame.setLayout(self.lo)

    def clear(self):
        for index in range(self.lo.count()):
            self.lo.itemAt(index).widget().deleteLater()
        self.setLayout(self.lo)
        self.contain_dice.clear()

    def auto_highlight(self, indexes: list):
        for index in indexes:
            self.contain_dice[index].set_state(True)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self.game.action_state == "cost":
            self.game.commit_button.setEnabled(False)
            choose_index = self.game.dice_zone.get_choose()
            cost_message = {"message": "check_cost", "cost": choose_index}
            self.game.socket_send(str(cost_message))

class AutoResizeWidget(QWidget):
    def __init__(self, parent, child_widget_size, layout, widget_type):
        super().__init__(parent)
        self.resize(child_widget_size, child_widget_size)
        self.frame = QFrame(self)
        self.frame.resize(child_widget_size, child_widget_size)
        self.layout_type = layout
        self.child_widget_size = child_widget_size
        if layout == "v":
            self.lo = QVBoxLayout()
        else:
            self.lo = QHBoxLayout()
        self.lo.setContentsMargins(0, 0, 0, 0)
        self.lo.setSpacing(0)
        self.widget_type = widget_type
        self.contain_widget = []

    def init_picture(self, obj: ClickableLabel, picture_name):
        category = ""
        if self.widget_type == "skill":
            category = "skills"
        elif self.widget_type == "energy":
            category = "energy"
        elif self.widget_type == "equip":
            category = "equip"
        elif self.widget_type == "element":
            category = "elements"
        picture = QPixmap("./resources/%s/%s.png" % (category, picture_name))
        obj.setPixmap(picture)

    def add_widget(self, widget_name):
        new_widget = ClickableLabel(self)
        new_widget.setScaledContents(True)
        self.init_picture(new_widget, widget_name)
        self.lo.addWidget(new_widget)
        self.contain_widget.append(new_widget)
        if self.layout_type == "v":
            self.resize(self.child_widget_size, self.child_widget_size * len(self.contain_widget))
        else:
            self.resize(self.child_widget_size  * len(self.contain_widget), self.child_widget_size)
        self.setLayout(self.lo)

    def clear(self):
        for index in range(self.lo.count()):
            self.lo.itemAt(index).widget().deleteLater()
        self.setLayout(self.lo)
        self.contain_widget.clear()

    def remove_widget(self, index):
        self.lo.itemAt(index).widget().deleteLater()
        self.contain_widget.pop(index)
        if self.layout_type == "v":
            self.resize(self.child_widget_size, self.child_widget_size * len(self.contain_widget))
        else:
            self.resize(self.child_widget_size  * len(self.contain_widget), self.child_widget_size)
        self.setLayout(self.lo)

class SkillZone(AutoResizeWidget):
    def __init__(self, parent: Gcg):
        super().__init__(parent, 80, "h", "skill")
        self.move(870, 610)
        self.choose: ClickableLabel|None = None
        self.game = parent

    def get_choose(self):
        if self.choose is not None:
            return self.contain_widget.index(self.choose)
        return None

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self.game.action_phase_start and self.game.action_state != "cost":
            obj = self.childAt(event.pos())
            if isinstance(obj, ClickableLabel):
                if obj.get_state():
                    if self.choose is not None:
                        try:
                            self.choose.set_state(False)
                        except RuntimeError:  # 对象已删除
                            pass
                    self.choose = obj
                    self.game.commit_button.show()
                    self.game.commit_button.setEnabled(False)
                    self.game.wait_change_state_obj = obj
                    self.game.action_state = "skill"
                    self.game.socket_send(str({"message": "check_skill_cost", "skill_index": self.get_choose()}))
                else:
                    self.choose = None
                    self.game.commit_button.hide()
                    self.game.wait_change_state_obj = None
                    self.game.action_state = ""

class SupportCard(QFrame):
    def __init__(self, parent):
        super().__init__(parent)
        self.resize(100, 100)
        self.pic = QLabel(self)
        self.pic.resize(100, 100)
        self.pic.setScaledContents(True)
        self.counter = QLabel(self)
        self.counter.resize(20, 20)
        self.counter.setFont(QFont('HYWenHei-85W', 14))
        self.counter.setStyleSheet('color: white')
        self.counter.setAlignment(Qt.AlignmentFlag.AlignCenter)

    @staticmethod
    def init_card_picture(obj: QLabel, picture_name):
        picture = QPixmap("./resources/cards/%s.png" % picture_name)
        obj.setPixmap(picture)

    def init(self, support_name, count):
        support_name = support_name.replace(" ", "")
        self.init_card_picture(self.pic, support_name)
        self.counter.setText(count)

    def change_count(self, value):
        self.counter.setText(value)

class SupportZone(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.resize(240, 240)
        self.lo = QGridLayout()
        # self.lo.setSpacing(10)
        self.lo.setRowStretch(0, 1)
        self.lo.setRowStretch(1, 1)
        self.lo.setColumnStretch(0, 1)
        self.lo.setColumnStretch(1, 1)
        self.contain_widget: list[SupportCard] = []

    def add_widget(self, support_name, count):
        new_support = SupportCard(self)
        new_support.init(support_name, count)
        self.contain_widget.append(new_support)
        num = len(self.contain_widget)
        self.lo.addWidget(new_support, (num-1)//2, (num-1)%2)
        self.setLayout(self.lo)

    def remove_widget(self, index):
        self.contain_widget.pop(index)
        self.lo.itemAt(index).widget().deleteLater()
        for index, widget in self.lo.count():
            self.lo.addWidget(widget, index//2, index%2)
        self.setLayout(self.lo)

    def change_support_count(self, index, value):
        self.contain_widget[index].change_count(value)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    game = Gcg()
    game.show()
    sys.exit(app.exec())

