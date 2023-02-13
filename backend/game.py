# Genius Invokation TCG, write in python.
# Copyright (C) 2023 Asassong

import random
from player import Player
from character import Character
from enums import ElementType, PlayerAction, GameStage, TimeLimit, EffectObj
from utils import read_json, pre_check, DuplicateDict
from typing import Union
from modify_manager import add_modify, invoke_modify, remove_modify, consume_modify_usage
import socket


class Game:
    def __init__(self, mode, player_socket: list, server_socket: socket.socket):
        self.config = read_json("config.json")
        game_config = self.config["Game"][mode]
        self.socket = server_socket
        self.client_socket = player_socket
        self.round = 0
        self.players: list[Player] = self.init_player(game_config["Player"], game_config["enable_deck"], game_config["enable_character"])
        self.first_player: int = -1
        self.init_card_num = game_config["init_card_num"]
        self.switch_hand_times = game_config["switch_hand_times"]
        self.switch_dice_times = game_config["switch_dice_times"]
        self.stage = GameStage.NONE
        self.state_dict = read_json("state.json")
        self.now_player = None
        self.max_round = game_config["max_round"]
        self.dead_info: set = set()

    def init_player(self, player_list, card_pack, char_pack):
        players = []
        for index, player in enumerate(player_list):
            players.append(Player(player, card_pack, char_pack))
            characters = players[-1].characters
            for char_index, character in enumerate(characters):
                init_message = {"message": "init_character", "position": char_index, "character_name": character.name,
                                "hp": character.get_hp(), "energy": (character.get_energy(), character.max_energy)}
                self.socket.sendto(str(init_message).encode(), self.client_socket[index])
                init_message = {"message": "init_oppo_character", "position": char_index,
                                "character_name": character.name,
                                "hp": character.get_hp(), "energy": (character.get_energy(), character.max_energy)}
                self.socket.sendto(str(init_message).encode(), self.client_socket[~index])
        return players

    def start_game(self):
        self.stage = GameStage.GAME_START
        for index, player in enumerate(self.players):
            player.draw(self.init_card_num)
            for _ in range(self.switch_hand_times):
                drop_cards = self.ask_player_redraw_card(player)
                player.redraw(drop_cards)
            cards = self.get_player_hand_card_info(player)
            add_card_message = {"message": "add_card", "cards": cards}
            self.socket.sendto(str(add_card_message).encode(), self.client_socket[index])
            oppo_card_num_message = {"message": "oppose_card_num", "num": len(cards)}
            self.socket.sendto(str(oppo_card_num_message).encode(), self.client_socket[~index])
            while True:
                character_index = self.ask_player_choose_character(player)
                state = player.choose_character(character_index)
                if state:
                    choose_message = {"message": "player_change_active", "change_from": None, "change_to": character_index}
                    self.socket.sendto(str(choose_message).encode(), self.client_socket[index])
                    choose_message = {"message": "oppose_change_active", "change_from": None,
                                      "change_to": character_index}
                    self.socket.sendto(str(choose_message).encode(), self.client_socket[~index])
                    active = player.get_active_character_obj()
                    skill = active.get_skills_type()
                    init_skill_message = {"message": "init_skill", "skills": skill}
                    self.socket.sendto(str(init_skill_message).encode(), self.client_socket[index])
                    break
        self.invoke_passive_skill()
        self.first_player = random.randint(0, len(self.players) - 1)
        self.start()

    def invoke_passive_skill(self):
        for player in self.players:
            self.now_player = self.players.index(player)
            characters = player.get_character()
            for character in characters:
                passive_skills = character.get_passive_skill()
                for passive in passive_skills:
                    self.handle_skill(character, passive)

    def start(self):
        while True:
            self.round += 1
            if not self.round % 2:
                hide_oppose_message = {"message": "hide_oppose"}
                for client in self.client_socket:
                    self.socket.sendto(str(hide_oppose_message).encode(), client)
            else:
                show_oppose_message = {"message": "show_oppose"}
                for client in self.client_socket:
                    self.socket.sendto(str(show_oppose_message).encode(), client)
            self.stage = GameStage.ROUND_START
            self.start_stage()
            self.stage = GameStage.ROLL
            self.roll_stage()
            self.stage = GameStage.ACTION
            self.action_stage()
            self.stage = GameStage.ROUND_END
            self.end_stage()
            if self.stage == GameStage.GAME_END:
                break

    def start_stage(self):
        self.now_player = self.first_player
        for _ in range(len(self.players)):
            print("start_stage")
            player = self.players[self.now_player]
            active = player.get_active_character_obj()
            start_stage_effect = invoke_modify(self, "start", active, player)
            self.handle_extra_effect("start", start_stage_effect)
            standby = player.get_standby_obj()
            for each in standby:
                start_stage_effect = invoke_modify(self, "start", each, player)
                self.handle_extra_effect("start", start_stage_effect)
            start_stage_effect = invoke_modify(self, "team_start", None, player)
            self.handle_extra_effect("start", start_stage_effect)
            if self.stage == GameStage.GAME_END:
                break
            for summon in player.summons:
                start_stage_effect = invoke_modify(self, "start", summon, player)
                self.handle_extra_effect("start", start_stage_effect)
            for support in player.supports:
                start_stage_effect = invoke_modify(self, "start", support, player)
                self.handle_extra_effect("start", start_stage_effect)

    def roll_stage(self):
        for index, player in enumerate(self.players):
            self.now_player = self.players.index(player)
            roll_effect = invoke_modify(self, "roll", None)
            if "FIXED_DICE" in roll_effect:
                player.roll(fixed_dice=roll_effect["FIXED_DICE"])
                roll_effect.pop("FIXED_DICE")
            else:
                player.roll()
            dices = self.get_player_dice_info(player)
            card_num_message = {"message": "show_dice_num", "num": len(dices)}
            self.socket.sendto(str(card_num_message).encode(), self.client_socket[index])
            card_num_message = {"message": "show_oppose_dice_num", "num": len(dices)}
            self.socket.sendto(str(card_num_message).encode(), self.client_socket[~index])
            extra_switch_times = 0
            if "REROLL" in roll_effect:
                if isinstance(roll_effect["REROLL"], str):
                    extra_switch_times += eval(roll_effect["REROLL"])
                    roll_effect.pop("REROLL")
            for _ in range(self.switch_dice_times + extra_switch_times):
                self.ask_player_reroll_dice(player)

    def action_stage(self):
        for player in self.players:
            player.round_has_end = False
        self.now_player = self.first_player
        while True:
            if self.stage == GameStage.GAME_END:
                break
            round_has_end = True
            action_type = None
            for player in self.players:
                if player.round_has_end:
                    continue
                else:
                    round_has_end = False
                    break
            if round_has_end:
                break
            now_player = self.players[self.now_player]
            if not now_player.round_has_end:
                active = now_player.get_active_character_obj()
                for modify_name, modify in active.modifies.copy().items():
                    consume_state = consume_modify_usage(modify, "act")
                    if consume_state == "remove":
                        remove_modify(active.modifies, modify_name)
                action_effect = invoke_modify(self, "action", active)
                if "USE_SKILL" in action_effect:
                    self.handle_skill(active, action_effect["USE_SKILL"])
                    action_effect.pop("USE_SKILL")
                action, extra = self.ask_player_action(now_player)
                if PlayerAction(action) == PlayerAction.END_ROUND:
                    others_had_end = False
                    for player in self.players:
                        if player.round_has_end:
                            others_had_end = True
                            break
                    now_player.round_has_end = True
                    if not others_had_end:
                        self.first_player = self.now_player
                elif PlayerAction(action) == PlayerAction.ELEMENT_TUNING:
                    self.element_tuning(now_player, extra)
                elif PlayerAction(action) == PlayerAction.CHANGE_CHARACTER:
                    change_state = self.player_change_avatar(now_player, extra)
                    change_from = now_player.current_character
                    print(("change_state", change_state))
                    if not change_state:
                        continue
                    elif change_state == "fast":
                        action_type = "fast"
                    now_player.choose_character(extra)
                    choose_message = {"message": "player_change_active", "change_from": change_from,
                                      "change_to": extra}
                    self.socket.sendto(str(choose_message).encode(), self.client_socket[self.now_player])
                    choose_message = {"message": "oppose_change_active", "change_from": change_from,
                                      "change_to": extra}
                    self.socket.sendto(str(choose_message).encode(), self.client_socket[~self.now_player])
                    clear_skill_message = {"message": "clear_skill"}
                    self.socket.sendto(str(clear_skill_message).encode(), self.client_socket[self.now_player])
                    active = now_player.get_active_character_obj()
                    skill = active.get_skills_type()
                    init_skill_message = {"message": "init_skill", "skills": skill}
                    self.socket.sendto(str(init_skill_message).encode(), self.client_socket[self.now_player])
                elif PlayerAction(action) == PlayerAction.USING_SKILLS:
                    use_state = self.use_skill(now_player, extra)
                    if not use_state:
                        continue
                elif PlayerAction(action) == PlayerAction.PLAY_CARD:
                    self.play_card(now_player, extra)
                if action_type is not None:
                    if action_type == "fast":
                        continue
                    else:
                        action_end_message = {"message": "act_end"}
                        self.socket.sendto(str(action_end_message).encode(), self.client_socket[self.now_player])
                        self.now_player = (self.now_player + 1) % len(self.players)
                else:
                    judge_action_type = self.judge_action(action)
                    if judge_action_type == "fast":
                        continue
                    else:
                        action_end_message = {"message": "act_end"}
                        self.socket.sendto(str(action_end_message).encode(), self.client_socket[self.now_player])
                        self.now_player = (self.now_player + 1) % len(self.players)
            else:
                action_end_message = {"message": "act_end"}
                self.socket.sendto(str(action_end_message).encode(), self.client_socket[self.now_player])
                self.now_player = (self.now_player + 1) % len(self.players)

    def end_stage(self):
        self.now_player = self.first_player
        for _ in range(len(self.players)):
            player = self.players[self.now_player]
            active = player.get_active_character_obj()
            end_stage_effect = invoke_modify(self, "end", active, player)
            self.handle_extra_effect("end", end_stage_effect)
            standby = player.get_standby_obj()
            for each in standby:
                end_stage_effect = invoke_modify(self, "end", each, player)
                self.handle_extra_effect("end", end_stage_effect)
            end_stage_effect = invoke_modify(self, "team_end", None, player)
            self.handle_extra_effect("end", end_stage_effect)
            need_remove_summon = []
            for summon in player.summons:
                effect = summon.effect
                print("summon_effect", effect)
                for each_effect in effect:
                    if "damage" in each_effect:
                        self.handle_damage(summon, "team", each_effect["damage"])
                    elif "heal" in each_effect:
                        self.handle_extra_effect("none", {"extra_effect": [({"HEAL": each_effect["heal"]}, each_effect["effect_obj"])]})
                    elif "application" in each_effect:
                        self.handle_extra_effect("none", {"extra_effect": [({"APPLICATION": each_effect["application"]}, each_effect["effect_obj"])]})
                summon_state = player.trigger_summon(summon, 1)
                if summon_state == "remove":
                    need_remove_summon.append(summon)
            for summon in need_remove_summon:
                player.summons.remove(summon)
            if self.stage == GameStage.GAME_END:
                break
            for summon in player.summons:
                end_stage_effect = invoke_modify(self, "end", summon, player)
                self.handle_extra_effect("end", end_stage_effect)
            for support in player.supports:
                end_stage_effect = invoke_modify(self, "end", support, player)
                self.handle_extra_effect("end", end_stage_effect)
            player.dices.clear()
            clear_dice_message = {"message": "clear_dice"}
            self.socket.sendto(str(clear_dice_message).encode(), self.client_socket[self.now_player])
            dice_num_message = {"message": "show_dice_num", "num": ""}
            self.socket.sendto(str(dice_num_message).encode(), self.client_socket[self.now_player])
            dice_num_message = {"message": "show_oppose_dice_num", "num": ""}
            self.socket.sendto(str(dice_num_message).encode(), self.client_socket[~self.now_player])
            player.draw(2)
            cards = self.get_player_hand_card_info(player)
            add_card_message = {"message": "add_card", "cards": cards[-2:]}
            self.socket.sendto(str(add_card_message).encode(), self.client_socket[self.now_player])
            oppo_card_num_message = {"message": "oppose_card_num", "num": len(cards)}
            self.socket.sendto(str(oppo_card_num_message).encode(), self.client_socket[~self.now_player])
            player.clear_character_saturation()
            self.now_player = (self.now_player + 1) % len(self.players)
        self.round_end_consume_modify()

    def get_now_player(self):
        return self.players[self.now_player]

    def get_oppose(self):
        return self.players[~self.now_player]

    @staticmethod
    def judge_input(input_, min_, max_):
        valid = []
        for each in input_:
            if each.isdigit():
                if min_ <= int(each) <= max_:
                    valid.append(int(each))
                else:
                    break
            else:
                break
        if len(list(set(valid))) == len(input_):
            return valid
        elif input_ == [""]:
            return []
        else:
            return False

    @staticmethod
    def judge_action(action_index):
        if action_index in [1, 3, 4]:
            return "combat"
        else:
            return "fast"

    @staticmethod
    def get_player_hand_card_info(player: Player) -> list[str]:
        hand = player.get_hand()
        card_info = []
        for card in hand:
            card_info.append(card.get_name())
        return card_info

    @staticmethod
    def get_player_character_info(player:Player) -> tuple[list[str], str]:
        character = player.get_character()
        names = []
        for c in character:
            names.append(c.name)
        active = player.get_active_character_name()
        return names, active

    @staticmethod
    def get_player_dice_info(player: Player) -> list[str]:
        dices = player.get_dice()
        dice_type = []
        for dice in dices:
            dice_type.append(ElementType(dice.element).name)
        return dice_type

    @staticmethod
    def get_player_character_detail(player: Player) -> str:
        character = player.get_character()
        detail = ""
        for c in character:
            detail += c.get_card_info()
        return detail

    def ask_player_redraw_card(self, player: Player):
        card_info = self.get_player_hand_card_info(player)
        redraw_message = {"message": "redraw", "hand": card_info}
        self.socket.sendto(str(redraw_message).encode(), self.client_socket[self.players.index(player)])
        oppo_card_num_message = {"message": "oppose_card_num", "num": len(self.get_player_hand_card_info(player))}
        self.socket.sendto(str(oppo_card_num_message).encode(), self.client_socket[~self.players.index(player)])
        while True:
            data, addr = self.socket.recvfrom(1024)
            if data:
                data = eval(data)
                if data["message"] == "selected_card":
                    return data["selected_card"]

    def ask_player_choose_card(self, player: Player):
        card_info = self.get_player_hand_card_info(player)
        s_card_info = ",".join(card_info)
        while True:
            print("%s, 您的手牌为 %s" % (player.name, s_card_info))
            index = input("请选择要打出的卡牌(0-%d):" % (len(card_info) - 1))
            card = self.judge_input(index, 0, len(card_info) - 1)
            if len(card) == 1:
                break
            else:
                print("输入格式错误，请重输")
        return card[0]

    def ask_player_choose_character(self, player: Player):
        select_message = {"message": "select_character"}
        self.socket.sendto(str(select_message).encode(), self.client_socket[self.players.index(player)])
        while True:
            data, addr = self.socket.recvfrom(1024)
            if data:
                data = eval(data)
                if data["message"] == "selected_character":
                    return data["character"]

    def ask_player_reroll_dice(self, player):
        dice_type = self.get_player_dice_info(player)
        reroll_message = {"message": "reroll", "now_dice": dice_type}
        self.socket.sendto(str(reroll_message).encode(), self.client_socket[self.players.index(player)])
        while True:
            data, addr = self.socket.recvfrom(1024)
            if data:
                data = eval(data)
                if data["message"] == "need_reroll":
                    player.reroll(data["need_reroll"])
                    index = self.players.index(player)
                    dices = self.get_player_dice_info(player)
                    clear_dice_message = {"message": "clear_dice"}
                    self.socket.sendto(str(clear_dice_message).encode(), self.client_socket[index])
                    dice_num_message = {"message": "show_dice_num", "num": len(dices)}
                    self.socket.sendto(str(dice_num_message).encode(), self.client_socket[index])
                    dice_num_message = {"message": "show_oppose_dice_num", "num": len(dices)}
                    self.socket.sendto(str(dice_num_message).encode(), self.client_socket[~index])
                    dice_message = {"message": "add_dice", "dices": dices}
                    self.socket.sendto(str(dice_message).encode(), self.client_socket[index])
                    break

    def ask_player_action(self, player: Player):
        action_message = {"message": "action_phase_start"}
        self.socket.sendto(str(action_message).encode(), self.client_socket[self.players.index(player)])
        while True:
            data, addr = self.socket.recvfrom(1024)
            if data:
                data = eval(data)
                # 1.使用角色技能2.元素调和3.结束回合4.切换角色5.打出卡牌
                if data["message"] == "selected_character":
                    return 4, data["character"]
                elif data["message"] == "play_card":
                    return 5, data["card_index"]
                elif data["message"] == "element_tuning":
                    return 2, data["card_index"]
                elif data["message"] == "round_end":
                    return 3, None
                elif data["message"] == "check_skill_cost":
                    active = player.get_active_character_obj()
                    skill_names = active.get_skills_name()
                    skill_name = skill_names[data["skill_index"]]
                    skill_detail = active.get_skill_detail(skill_name)
                    skill_cost = skill_detail["cost"].copy()
                    skill_type = skill_detail["type"]
                    use_skill_effect = invoke_modify(self, "use_skill", active, use=False, skill_name=skill_name,
                                                     skill_type=skill_type, cost=skill_cost)
                    real_cost = use_skill_effect["cost"]
                    state = player.check_cost(real_cost)
                    if state or state == {}:
                        enable_message = {"message": "enable_commit"}
                        self.socket.sendto(str(enable_message).encode(), self.client_socket[self.players.index(player)])
                elif data["message"] == "use_skill":
                    return 1, data["skill_index"]

    def ask_player_remove_summon(self, player: Player):
        summon = player.get_summon_name()
        s_summon = ",".join(summon)
        while True:
            print("%s" % player.name)
            print("您的召唤物为 %s" % s_summon)
            index = input("请选择要移除的召唤物(0-%d, 空格隔开):" % (len(summon) - 1))
            valid_index = self.judge_input(index, 0, len(summon) - 1)
            if len(valid_index) == 1:
                break
            else:
                print("输入格式错误，请重输")
        return valid_index[0]

    def ask_player_remove_support(self, player: Player):
        support = player.get_support_name()
        s_support = ",".join(support)
        while True:
            print("%s" % player.name)
            print("您的支援卡为 %s" % s_support)
            index = input("请选择要移除的支援卡(0-%d, 空格隔开):" % (len(support) - 1))
            valid_index = self.judge_input(index, 0, len(support) - 1)
            if len(valid_index) == 1:
                break
            else:
                print("输入格式错误，请重输")
        return valid_index[0]

    def element_tuning(self, player: Player, card_index):
        state = self.no_skill_cost({"ANY": 1})
        if state:
            element = player.get_active_character_obj().element
            player.append_special_dice(element)
            dice_message = {"message": "add_dice", "dices": [element.name]}
            self.socket.sendto(str(dice_message).encode(), self.client_socket[self.players.index(player)])
            player.remove_hand_card(card_index)
            remove_card_message = {"message": "remove_card", "card_index": card_index}
            self.socket.sendto(str(remove_card_message).encode(), self.client_socket[self.players.index(player)])
            oppo_card_num_message = {"message": "oppose_card_num", "num": len(self.get_player_hand_card_info(player))}
            self.socket.sendto(str(oppo_card_num_message).encode(), self.client_socket[~self.players.index(player)])
            dices = self.get_player_dice_info(player)
            dice_num_message = {"message": "show_dice_num", "num": len(dices)}
            self.socket.sendto(str(dice_num_message).encode(), self.client_socket[self.players.index(player)])
            dice_num_message = {"message": "show_oppose_dice_num", "num": len(dices)}
            self.socket.sendto(str(dice_num_message).encode(), self.client_socket[~self.players.index(player)])

    def no_skill_cost(self, cost):
        player = self.get_now_player()
        dice_type = self.get_player_dice_info(player)
        cost_state = player.check_cost(cost)
        if cost_state:
            cost_indexes = []
            for key, value in cost_state.items():
                start_index = 0
                for _ in range(value):
                    new_index = dice_type.index(key, start_index)
                    cost_indexes.append(new_index)
                    start_index = new_index + 1
            cost_message = {"message": "highlight_dice", "dice_indexes": cost_indexes}
            self.socket.sendto(str(cost_message).encode(), self.client_socket[self.players.index(player)])
            while True:
                data, addr = self.socket.recvfrom(1024)
                if data:
                    data = eval(data)
                    if data["message"] == "commit_cost":
                        player.use_dices(data["cost"])
                        consume_message = {"message": "remove_dice", "dices": data["cost"]}
                        self.socket.sendto(str(consume_message).encode(),
                                           self.client_socket[self.players.index(player)])
                        dices = self.get_player_dice_info(player)
                        dice_num_message = {"message": "show_dice_num", "num": len(dices)}
                        self.socket.sendto(str(dice_num_message).encode(),
                                           self.client_socket[self.players.index(player)])
                        dice_num_message = {"message": "show_oppose_dice_num", "num": len(dices)}
                        self.socket.sendto(str(dice_num_message).encode(),
                                           self.client_socket[~self.players.index(player)])
                        return True
                    elif data["message"] == "check_cost":
                        check_result = player.recheck_cost(cost, data["cost"])
                        if check_result:
                            enable_message = {"message": "enable_commit"}
                            self.socket.sendto(str(enable_message).encode(),
                                               self.client_socket[self.players.index(player)])
                    elif data["message"] == "cancel":
                        return False
        elif cost_state == {}:
            return True

    def player_change_avatar(self, player: Player, character_index):
        normal_cost = {"ANY": 1}
        change_action = "combat"
        active = player.get_active_character_obj()
        new_active = character_index
        if player.check_character_alive(new_active):
            change_cost_effect = invoke_modify(self, "change_cost", active, cost=normal_cost, change_from=active, change_to=player.characters[new_active])
            cost_state = self.no_skill_cost(change_cost_effect["cost"])
            change_cost_effect.pop("cost")
            if cost_state:
                change_action_effect = invoke_modify(self, "change", active, change_from=active, change_to=player.characters[new_active])
                if "change_action" in change_action_effect:
                    change_action = change_action_effect["change_action"]
            else:
                return False
        else:
            return False
        return change_action

    def use_skill(self, player: Player, skill_index):
        active = player.get_active_character_obj()
        skill_names = active.get_skills_name()
        skill_name = skill_names[skill_index]
        use_state = self.handle_skill(active, skill_name)
        if use_state:
            return True
        else:
            return False

    def skill_cost(self, skill_cost):
        player = self.get_now_player()
        active = player.get_active_character_obj()
        state = player.check_cost(skill_cost)
        if state:
            dice_type = self.get_player_dice_info(player)
            use_energy = -1
            if "ENERGY" in state:
                use_energy = state["ENERGY"]
            cost_indexes = []
            for key, value in state.items():
                if key != "ENERGY":
                    start_index = 0
                    for _ in range(value):
                        new_index = dice_type.index(key, start_index)
                        cost_indexes.append(new_index)
                        start_index = new_index + 1
            cost_message = {"message": "highlight_dice", "dice_indexes": cost_indexes}
            self.socket.sendto(str(cost_message).encode(), self.client_socket[self.players.index(player)])
            while True:
                data, addr = self.socket.recvfrom(1024)
                if data:
                    data = eval(data)
                    if data["message"] == "commit_cost":
                        player.use_dices(data["cost"])
                        consume_message = {"message": "remove_dice", "dices": data["cost"]}
                        self.socket.sendto(str(consume_message).encode(),
                                           self.client_socket[self.players.index(player)])
                        dices = self.get_player_dice_info(player)
                        dice_num_message = {"message": "show_dice_num", "num": len(dices)}
                        self.socket.sendto(str(dice_num_message).encode(),
                                           self.client_socket[self.players.index(player)])
                        dice_num_message = {"message": "show_oppose_dice_num", "num": len(dices)}
                        self.socket.sendto(str(dice_num_message).encode(),
                                           self.client_socket[~self.players.index(player)])
                        if use_energy != -1:
                            active.change_energy(-use_energy)
                            char_index = player.current_character
                            energy = (active.get_energy(), active.max_energy)
                            change_energy_message = {"message": "change_energy", "position": char_index, "energy": energy}
                            self.socket.sendto(str(change_energy_message).encode(), self.client_socket[~self.players.index(player)])
                            change_energy_message = {"message": "oppose_change_energy", "position": char_index,
                                                     "energy": energy}
                            self.socket.sendto(str(change_energy_message).encode(),
                                               self.client_socket[~self.players.index(player)])
                        return True
                    elif data["message"] == "check_cost":
                        check_result = player.recheck_cost(skill_cost, data["cost"])
                        if check_result:
                            enable_message = {"message": "enable_commit"}
                            self.socket.sendto(str(enable_message).encode(),
                                               self.client_socket[self.players.index(player)])
                    elif data["message"] == "cancel":
                        return False
        elif state == {}:
            pass
        else:
            return False
        return True

    def play_card(self, player: Player, card_index):
        card = player.get_card_obj(card_index)
        effect_obj = card.effect_obj
        card_cost = card.get_cost().copy()
        tag = card.tag
        cost_effect = invoke_modify(self, "card_cost", card, player, card_tag=tag, cost=card_cost)
        card_cost = cost_effect["cost"]
        state = player.check_cost(card_cost)
        cost_effect.pop("cost")
        if state or state == {}:
            obj = None
            if effect_obj == "select":
                char_index = self.ask_player_choose_character(player)
                obj = player.characters[char_index]
            elif effect_obj == "summon":
                summon_index = self.ask_player_remove_summon(player)
                obj = player.summons[summon_index]
            elif effect_obj == "oppose":
                oppose = self.players[~self.now_player]
                char_index = self.ask_player_choose_character(oppose)
                obj = player.characters[char_index]
            elif effect_obj == "oppose_summon":
                oppose = self.players[~self.now_player]
                summon_index = self.ask_player_remove_summon(oppose)
                obj = player.summons[summon_index]
            elif effect_obj == "all_summon":
                pass
            elif effect_obj == "player":
                pass
            elif isinstance(effect_obj, list):
                pass
            if card.combat_limit:
                pass

            if "Location" in tag or "Companion" in tag or "Item" in tag:
                for add_state in player.add_support(card):
                    if add_state == "remove":
                        index = self.ask_player_remove_support(player)
                        player.remove_support(index)
            elif "Food" in tag:
                if isinstance(obj, Character):
                    if obj.get_saturation() < player.max_character_saturation:
                        obj.change_saturation("+1")
                    else:
                        return False
                else:
                    return False
            elif "Weapon" in tag:
                if isinstance(obj, Character):
                    if obj.weapon not in tag:
                        return False
                else:
                    return False
            if card.use_skill:
                cost_state = self.skill_cost(card_cost)
            else:
                cost_state = self.no_skill_cost(card_cost)
            if not cost_state:
                return False
            self.handle_extra_effect("card_cost", cost_effect)
            player.remove_hand_card(card_index)
            remove_card_message = {"message": "remove_card", "card_index": card_index}
            self.socket.sendto(str(remove_card_message).encode(), self.client_socket[self.players.index(player)])
            oppo_card_num_message = {"message": "oppose_card_num", "num": len(self.get_player_hand_card_info(player))}
            self.socket.sendto(str(oppo_card_num_message).encode(), self.client_socket[~self.players.index(player)])
            modifies, modify_name = card.init_modify()
            if "Weapon" in tag or "Artifact" in tag or "Talent" in tag:
                if isinstance(obj, Character):
                    equip = list(set(tag) & {"Weapon", "Artifact", "Talent"})[0].lower()
                    if obj.equipment[equip] is not None:
                        remove_modify(obj.modifies, obj.equipment[equip], "main")
                    obj.equipment[equip] = card.get_name()
                    add_modify(self, obj, modifies, modify_name)
                    equipment = [type_.lower() for type_, value in obj.equipment.items() if value is not None]
                    update_equip_message = {"message": "update_equip", "position": player.characters.index(obj),  "equip": equipment}
                    self.socket.sendto(str(update_equip_message).encode(), self.client_socket[self.now_player])
                    update_equip_message = {"message": "oppose_update_equip", "position": player.characters.index(obj),
                                            "equip": equipment}
                    self.socket.sendto(str(update_equip_message).encode(), self.client_socket[~self.now_player])
            elif "Location" in tag or "Companion" in tag or "Item" in tag:
                if card.counter:
                    for key, value in card.counter.items():
                        init_support_message = {"message": "init_support", "support_name": card.get_name(), "count": str(value)}
                        self.socket.sendto(str(init_support_message).encode(), self.client_socket[self.now_player])
                        init_support_message = {"message": "init_oppose_support", "support_name": card.get_name(),
                                                "count": str(value)}
                        self.socket.sendto(str(init_support_message).encode(), self.client_socket[~self.now_player])
                else:
                    init_support_message = {"message": "init_support", "support_name": card.get_name(),
                                            "count": ""}
                    self.socket.sendto(str(init_support_message).encode(), self.client_socket[self.now_player])
                    init_support_message = {"message": "init_oppose_support", "support_name": card.get_name(),
                                            "count": ""}
                    self.socket.sendto(str(init_support_message).encode(), self.client_socket[~self.now_player])
                add_modify(self, card, modifies, modify_name)
            elif "Food" in tag:
                add_modify(self, obj, modifies, modify_name)
            else:
                add_modify(self, card, modifies, modify_name)
            if card.use_skill:
                self.handle_skill(self.get_now_player().get_active_character_obj(), card.use_skill)
        else:
            return False
        return True


    def handle_skill(self, invoker, skill_name):
        skill_detail = invoker.get_skill_detail(skill_name)
        skill_cost = skill_detail["cost"].copy()
        skill_type = skill_detail["type"]
        if "Normal Attack" in skill_type or "Elemental Skill" in skill_type:
            add_energy = 1
        else:
            add_energy = 0
        use_skill_effect = invoke_modify(self, "use_skill", invoker, skill_name=skill_name, skill_type=skill_type, cost=skill_cost, add_energy=add_energy)
        if "cost" in use_skill_effect:
            real_cost = use_skill_effect["cost"]
            cost_state = self.skill_cost(real_cost)
            use_skill_effect.pop("cost")
        else:
            cost_state = self.skill_cost(skill_cost)
        if not cost_state:
            return False
        if "add_energy" in use_skill_effect:
            invoker.change_energy(use_skill_effect["add_energy"])
            use_skill_effect.pop("add_energy")
        else:
            invoker.change_energy(add_energy)
        player = self.get_now_player()
        char_index = player.characters.index(invoker)  # 被动技能， 不为出战角色
        energy = (invoker.get_energy(), invoker.max_energy)
        change_energy_message = {"message": "change_energy", "position": char_index, "energy": energy}
        self.socket.sendto(str(change_energy_message).encode(), self.client_socket[self.players.index(player)])
        change_energy_message = {"message": "oppose_change_energy", "position": char_index,
                                 "energy": energy}
        self.socket.sendto(str(change_energy_message).encode(),
                           self.client_socket[~self.players.index(player)])
        left_effect = self.handle_extra_effect("use_skill", use_skill_effect)
        if "modify" in skill_detail:
            add_modify(self, invoker, skill_detail["modify"], skill_name)
        if "damage" in skill_detail:
            self.handle_damage(invoker, "team", skill_detail["damage"], skill_type=skill_type, skill_name=skill_name, left_effect=left_effect)
        if "create" in skill_detail:
            self.handle_state(invoker, skill_detail["create"])
        if "summon" in skill_detail:
            self.handle_summon(self.get_now_player(), skill_detail["summon"])
        return True

    def handle_damage(self, attacker, attackee: Union[str, Character], damage: dict[str, int], **kwargs):
        oppose = self.get_oppose()
        extra_attack = DuplicateDict()
        print("damage", damage)
        if attackee == "team":
            oppose_active = oppose.get_active_character_obj()
        else:
            oppose_active = attackee
        for element_type, init_damage in damage.items():
            if element_type in ElementType.__members__:
                # TODO 也要传infusion
                reaction_effect = self.handle_element_reaction(oppose_active, element_type)
                effects = next(reaction_effect)
                reaction = effects["reaction"]
                for key, value in effects.items():
                    if key == element_type:
                        init_damage += eval(effects[key])
                    elif key in ["HYDRO_DMG", "GEO_DMG", "ELECTRO_DMG","DENDRO_DMG", "PYRO_DMG", "PHYSICAL_DMG",
                                "CRYO_DMG", "ANEMO_DMG", "PIERCE_DMG"]:
                        extra_attack.update({key.replace("_DMG", ""): value})
                attack_effect = invoke_modify(self, "attack", attacker, **kwargs, reaction=reaction, damage=init_damage, element=element_type)
                damage = attack_effect["damage"]
                attack_effect.pop("damage")
                self.handle_extra_effect("attack", attack_effect)
                attackee_effect = invoke_modify(self, "defense", oppose_active, **kwargs, reaction=reaction, hurt=damage,
                                              element=element_type)
                hurt = attackee_effect["hurt"]
                attackee_effect.pop("hurt")
                self.handle_extra_effect("defense", attackee_effect)
                shield_effect = invoke_modify(self, "shield", oppose_active, **kwargs, hurt=hurt)
                hurt = shield_effect["hurt"]
                oppose_state = oppose_active.change_hp(-hurt)
                characters = self.get_oppose().characters
                change_hp_message = {"message": "change_hp", "position": characters.index(oppose_active), "hp": oppose_active.get_hp()}
                self.socket.sendto(str(change_hp_message).encode(), self.client_socket[~self.now_player])
                change_hp_message = {"message": "oppose_change_hp", "position": characters.index(oppose_active),
                                     "hp": oppose_active.get_hp()}
                self.socket.sendto(str(change_hp_message).encode(), self.client_socket[self.now_player])
                if oppose_state == "die":
                    self.handle_oppose_dead(oppose)
                next(reaction_effect)
            elif element_type == "PHYSICAL":
                infusion_effect = invoke_modify(self, "infusion", attacker, **kwargs)
                if "infusion" in infusion_effect:
                    infusion = infusion_effect["infusion"]
                    infusion_effect.pop("infusion")
                    left_effect = self.handle_extra_effect("infusion", infusion_effect)
                    self.handle_damage(attacker, attackee, {infusion: init_damage}, **kwargs, left_effect=left_effect)
                else:
                    attack_effect = invoke_modify(self, "attack", attacker, **kwargs, reaction=None,
                                                  damage=init_damage, element=element_type)
                    damage = attack_effect["damage"]
                    attack_effect.pop("damage")
                    self.handle_extra_effect("attack", attack_effect)
                    attackee_effect = invoke_modify(self, "defense", oppose_active, **kwargs, reaction=None,
                                                    hurt=damage, element=element_type)
                    hurt = attackee_effect["hurt"]
                    attackee_effect.pop("hurt")
                    self.handle_extra_effect("defense", attackee_effect)
                    shield_effect = invoke_modify(self, "shield", oppose_active, **kwargs, hurt=hurt)
                    hurt = shield_effect["hurt"]
                    oppose_state = oppose_active.change_hp(-hurt)
                    characters = self.get_oppose().characters
                    change_hp_message = {"message": "change_hp", "position": characters.index(oppose_active),
                                         "hp": oppose_active.get_hp()}
                    self.socket.sendto(str(change_hp_message).encode(), self.client_socket[~self.now_player])
                    change_hp_message = {"message": "oppose_change_hp", "position": characters.index(oppose_active),
                                         "hp": oppose_active.get_hp()}
                    self.socket.sendto(str(change_hp_message).encode(), self.client_socket[self.now_player])
                    if oppose_state == "die":
                        self.handle_oppose_dead(oppose)
            elif element_type == "PIERCE":
                if attackee == "team":
                    oppose_standby = oppose.get_standby_obj()
                else:
                    oppose_standby = [attackee]
                # TODO 穿透伤害不能改变伤害，但是可能有其他效果
                for obj in oppose_standby:
                    oppose_state = obj.change_hp(-init_damage)
                    characters = self.get_oppose().characters
                    change_hp_message = {"message": "change_hp", "position": characters.index(obj),
                                         "hp": obj.get_hp()}
                    self.socket.sendto(str(change_hp_message).encode(), self.client_socket[~self.now_player])
                    change_hp_message = {"message": "oppose_change_hp", "position": characters.index(obj),
                                         "hp": obj.get_hp()}
                    self.socket.sendto(str(change_hp_message).encode(), self.client_socket[self.now_player])
                    if oppose_state == "die":
                        self.handle_oppose_dead(oppose)
        if extra_attack:
            oppose_other = oppose.get_character().copy()
            oppose_other.remove(oppose_active)
            for key, value in extra_attack.items():
                for standby in oppose_other:
                    self.handle_damage(attacker, standby, {key: value})
        extra_effect = invoke_modify(self, "extra_attack", attacker, None)
        if "extra_attack" in extra_effect:
            for element, damage in extra_effect["extra_attack"]:
                self.handle_damage(attacker, "team", {element: damage})
            extra_effect.pop("extra_attack")
        self.handle_extra_effect("extra_attack", extra_effect)
        after_attack_effect = invoke_modify(self, "after_attack", None, None)
        self.handle_extra_effect("after_attack", after_attack_effect)

    def handle_oppose_dead(self, oppose: Player):
        end = True
        for index in range(len(oppose.get_character())):
            if oppose.check_character_alive(index):
                end = False
                break
        if end:
            self.stage = GameStage.GAME_END
        else:
            change_from = oppose.get_active_character_obj()
            if not oppose.get_active_character_obj().alive:
                while True:
                    character_index = self.ask_player_choose_character(oppose)
                    if oppose.choose_character(character_index):
                        break
            change_to = oppose.get_active_character_obj()
            if change_from != change_to:
                change_action_effect = invoke_modify(self, "change", change_from,
                                                     change_from=change_from,
                                                     change_to=change_to, left_effect={"change_action": "fast"})
                choose_message = {"message": "oppose_change_active",
                                  "change_from": oppose.characters.index(change_from),
                                  "change_to": oppose.characters.index(change_to)}
                self.socket.sendto(str(choose_message).encode(),
                                   self.client_socket[self.now_player])
                choose_message = {"message": "player_change_active",
                                  "change_from": oppose.characters.index(change_from),
                                  "change_to": oppose.characters.index(change_to)}
                self.socket.sendto(str(choose_message).encode(),
                                   self.client_socket[~self.now_player])
                clear_skill_message = {"message": "clear_skill"}
                self.socket.sendto(str(clear_skill_message).encode(),
                                   self.client_socket[~self.now_player])
                active = oppose.get_active_character_obj()
                skill = active.get_skills_type()
                init_skill_message = {"message": "init_skill", "skills": skill}
                self.socket.sendto(str(init_skill_message).encode(),
                                   self.client_socket[~self.now_player])
                self.handle_extra_effect("change", change_action_effect)
            self.dead_info.add(oppose)

    def handle_state(self, invoker: Character, combat_state):
        # TODO modify修改modify
        for state_name, num in combat_state.items():
            modify = self.state_dict[state_name]["modify"]
            for _ in range(num):
                add_modify(self, invoker, modify, state_name)

    def handle_summon(self, player: Player, summon_dict: dict):
        for summon_name, num in summon_dict.items():
            for _ in range(num):
                for add_state in player.add_summon(summon_name):
                    if add_state == "remove":
                        index = self.ask_player_remove_summon(player)
                        player.remove_summon(index)
                summon_obj = player.summons[-1]
                summon_modify = summon_obj.init_modify()
                if summon_modify is not None:
                    modifies, summon = summon_modify
                    add_modify(self, summon_obj, modifies, summon)

    def handle_element_reaction(self, trigger_obj: Character, element, type_="oppose"):
        trigger_obj.application.append(ElementType[element])
        applied_element = set(trigger_obj.application)
        # 反应顺序还需进一步测试
        if {ElementType.CRYO, ElementType.PYRO}.issubset(applied_element):
            applied_element.remove(ElementType.CRYO)
            applied_element.remove(ElementType.PYRO)
            yield {"CRYO": "+2", "PYRO": "+2", "reaction": "MELT"}
        elif {ElementType.HYDRO, ElementType.PYRO}.issubset(applied_element):
            applied_element.remove(ElementType.PYRO)
            applied_element.remove(ElementType.HYDRO)
            yield {"HYDRO": "+2", "PYRO": "+2", "reaction": "VAPORIZE"}
        elif {ElementType.ELECTRO, ElementType.PYRO}.issubset(applied_element):
            applied_element.remove(ElementType.ELECTRO)
            applied_element.remove(ElementType.PYRO)
            yield {"ELECTRO": "+2", "PYRO": "+2", "reaction": "OVERLOADED"}
            if type_ == "oppose":
                add_modify(self, trigger_obj, [{"category": "after_attack", "condition":["IS_ACTIVE"], "effect":{"CHANGE_CHARACTER": -1}, "effect_obj":"OPPOSE", "time_limit":{"IMMEDIATE": 1}}], "OVERLOADED")
            else:
                add_modify(self, trigger_obj, [
                    {"category": "after_attack", "condition": ["IS_ACTIVE"], "effect": {"CHANGE_CHARACTER": -1},
                     "effect_obj": "ALL", "time_limit": {"IMMEDIATE": 1}}], "OVERLOADED")
        elif {ElementType.HYDRO, ElementType.CRYO}.issubset(applied_element):
            applied_element.remove(ElementType.HYDRO)
            applied_element.remove(ElementType.CRYO)
            yield {"HYDRO": "+1", "CRYO": "+1", "reaction": "FROZEN"}
            if type_ == "oppose":
                add_modify(self, trigger_obj, [{"category": "action", "condition":[], "effect":{"FROZEN": "TRUE"}, "effect_obj":"OPPOSE_SELF", "time_limit":{"DURATION": 1}},
                                               {"category": "defense", "condition":[["BEING_HIT_BY", "PHYSICAL", "PYRO"]], "effect":{"FROZEN": "FALSE", "HURT": "+2"}, "effect_obj":"OPPOSE_SELF", "time_limit":{"DURATION": 1}}], "FROZEN")
            else:
                add_modify(self, trigger_obj, [
                    {"category": "action", "condition": [], "effect": {"FROZEN": "TRUE"}, "effect_obj": "SELF",
                     "time_limit": {"DURATION": 1}},
                    {"category": "defense", "condition": [["BEING_HIT_BY", "PHYSICAL", "PYRO"]],
                     "effect": {"FROZEN": "FALSE", "HURT": "+2"}, "effect_obj": "SELF",
                     "time_limit": {"DURATION": 1}}], "FROZEN")
        elif {ElementType.ELECTRO, ElementType.CRYO}.issubset(applied_element):
            applied_element.remove(ElementType.CRYO)
            applied_element.remove(ElementType.ELECTRO)
            yield {"ELECTRO": "+1", "CRYO": "+1", "PIERCE_DMG": 1, "reaction": "SUPER_CONDUCT"}
        elif {ElementType.ELECTRO, ElementType.HYDRO}.issubset(applied_element):
            applied_element.remove(ElementType.ELECTRO)
            applied_element.remove(ElementType.HYDRO)
            yield {"ELECTRO": "+1", "HYDRO": "+1", "PIERCE_DMG": 1, "reaction": "ELECTRO_CHARGE"}
        elif {ElementType.DENDRO, ElementType.PYRO}.issubset(applied_element):
            applied_element.remove(ElementType.DENDRO)
            applied_element.remove(ElementType.PYRO)
            yield {"DENDRO": "+1", "PYRO": "+1", "reaction": "BURNING"}
            if type_ == "oppose":
                self.handle_summon(self.get_now_player(), {"Burning Flame": 1})
            else:
                self.handle_summon(self.get_oppose(), {"Burning Flame": 1})
        elif {ElementType.DENDRO, ElementType.HYDRO}.issubset(applied_element):
            applied_element.remove(ElementType.DENDRO)
            applied_element.remove(ElementType.HYDRO)
            yield {"DENDRO": "+1", "HYDRO": "+1", "reaction": "BLOOM"}
            if type_ == "oppose":
                self.handle_state(self.get_now_player().get_active_character_obj(), {"Dendro Core": 1})
            else:
                self.handle_state(self.get_oppose().get_active_character_obj(), {"Dendro Core": 1})
        elif {ElementType.DENDRO, ElementType.ELECTRO}.issubset(applied_element):
            applied_element.remove(ElementType.DENDRO)
            applied_element.remove(ElementType.ELECTRO)
            yield {"DENDRO": "+1", "ELECTRO": "+1", "reaction": "CATALYZE"}
            if type_ == "oppose":
                self.handle_state(self.get_now_player().get_active_character_obj(), {"Catalyzing Field": 2})
            else:
                self.handle_state(self.get_oppose().get_active_character_obj(), {"Catalyzing Field": 2})
        elif ElementType.ANEMO in applied_element:
            applied_element.remove(ElementType.ANEMO)
            elements = list(applied_element)
            for element in elements:
                if element != ElementType.DENDRO:
                    applied_element.remove(element)
                    yield {element.name + "_DMG": 1, "reaction": "SWIRL", "swirl_element": element.name}
                    break
        elif ElementType.GEO in applied_element:
            applied_element.remove(ElementType.GEO)
            elements = list(applied_element)
            for element in elements:
                if element != ElementType.DENDRO:
                    applied_element.remove(element)
                    yield {"GEO": "+1", "reaction": "CRYSTALLIZE", "crystallize_element": element.name}
                    add_modify(self, trigger_obj, [{"category": "shield", "condition":[], "effect":{"SHIELD": 1}, "effect_obj":"ACTIVE", "time_limit":{"USE_UP": 1}, "stack": 2 ,"repeated": "True"}], "CRYSTALLIZE")
                    break
        else:
            yield {"reaction": None}
        trigger_obj.application = list(applied_element)
        application = [elementType.name.lower() for elementType in trigger_obj.application]
        if type_ == "oppose":
            characters = self.get_oppose().characters
            application_message = {"message": "oppose_change_application", "position": characters.index(trigger_obj), "application": application}
            self.socket.sendto(str(application_message).encode(), self.client_socket[self.now_player])
            application_message = {"message": "change_application", "position": characters.index(trigger_obj),
                                   "application": application}
            self.socket.sendto(str(application_message).encode(), self.client_socket[~self.now_player])
        else:
            characters = self.get_now_player().characters
            application_message = {"message": "change_application", "position": characters.index(trigger_obj),
                                   "application": application}
            self.socket.sendto(str(application_message).encode(), self.client_socket[self.now_player])
            application_message = {"message": "oppose_change_application", "position": characters.index(trigger_obj),
                                   "application": application}
            self.socket.sendto(str(application_message).encode(), self.client_socket[~self.now_player])
        yield

    def handle_extra_effect(self, operation, effect: dict):
        player = self.get_now_player()
        oppose = self.get_oppose()
        left_effect = {}
        for effect_type, effect_value in effect.items():
            if effect_type == "extra_effect":
                for each in effect_value:
                    print("extra_effect", each)
                    extra_effect, effect_obj = each
                    if effect_obj == "PLAYER":
                        if "DRAW_CARD" in extra_effect:
                            card = extra_effect["DRAW_CARD"]
                            if isinstance(card, int):
                                player.draw(card)
                                cards = self.get_player_hand_card_info(player)
                                add_card_message = {"message": "add_card", "cards": cards[-card:]}
                                self.socket.sendto(str(add_card_message).encode(), self.client_socket[self.now_player])
                                oppo_card_num_message = {"message": "oppose_card_num", "num": len(cards)}
                                self.socket.sendto(str(oppo_card_num_message).encode(),
                                                   self.client_socket[~self.now_player])
                            else:
                                if card.startswith("TYPE_"):
                                    card_type = card.replace("TYPE_", "")
                                    player.draw_type(card_type)
                                    cards = self.get_player_hand_card_info(player)
                                    add_card_message = {"message": "add_card", "cards": cards[-1:]}
                                    self.socket.sendto(str(add_card_message).encode(),
                                                       self.client_socket[self.now_player])
                                    oppo_card_num_message = {"message": "oppose_card_num", "num": len(cards)}
                                    self.socket.sendto(str(oppo_card_num_message).encode(),
                                                       self.client_socket[~self.now_player])
                        if "ADD_CARD" in extra_effect:
                            player.append_hand_card(extra_effect["ADD_CARD"])
                            cards = self.get_player_hand_card_info(player)
                            add_card_message = {"message": "add_card", "cards": cards[-1:]}
                            self.socket.sendto(str(add_card_message).encode(),
                                               self.client_socket[self.now_player])
                            oppo_card_num_message = {"message": "oppose_card_num", "num": len(cards)}
                            self.socket.sendto(str(oppo_card_num_message).encode(),
                                               self.client_socket[~self.now_player])
                        if "APPEND_DICE" in extra_effect:
                            dices = extra_effect["APPEND_DICE"]
                            if isinstance(dices, list):
                                for dice in dices:
                                    if dice == "RANDOM":
                                        player.append_random_dice()
                                    elif dice == "BASE":
                                        player.append_base_dice()
                                    else:
                                        player.append_special_dice(dice)
                                    dices = self.get_player_dice_info(player)
                                    dice_num_message = {"message": "show_dice_num", "num": len(dices)}
                                    self.socket.sendto(str(dice_num_message).encode(), self.client_socket[self.now_player])
                                    dice_num_message = {"message": "show_oppose_dice_num", "num": len(dices)}
                                    self.socket.sendto(str(dice_num_message).encode(), self.client_socket[~self.now_player])
                                    dice_message = {"message": "add_dice", "dices": dices[-1:]}
                                    self.socket.sendto(str(dice_message).encode(), self.client_socket[self.now_player])
                            else:
                                if dices == "RANDOM":
                                    player.append_random_dice()
                                elif dices == "BASE":
                                    player.append_base_dice()
                                else:
                                    player.append_special_dice(dices)
                                dices = self.get_player_dice_info(player)
                                dice_num_message = {"message": "show_dice_num", "num": len(dices)}
                                self.socket.sendto(str(dice_num_message).encode(), self.client_socket[self.now_player])
                                dice_num_message = {"message": "show_oppose_dice_num", "num": len(dices)}
                                self.socket.sendto(str(dice_num_message).encode(), self.client_socket[~self.now_player])
                                dice_message = {"message": "add_dice", "dices": dices[-1:]}
                                self.socket.sendto(str(dice_message).encode(), self.client_socket[self.now_player])
                    else:
                        if "CHANGE_CHARACTER" in extra_effect:
                            if effect_obj == "OPPOSE":
                                change_from = oppose.get_active_character_obj()
                                oppose.auto_change_active(extra_effect["CHANGE_CHARACTER"])
                                change_to = oppose.get_active_character_obj()
                                if change_from != change_to:
                                    change_action_effect = invoke_modify(self, "change", change_from,
                                                                         change_from=change_from,
                                                                         change_to=change_to, left_effect={"change_action": "fast"})
                                    choose_message = {"message": "oppose_change_active", "change_from": oppose.characters.index(change_from),
                                                      "change_to": oppose.characters.index(change_to)}
                                    self.socket.sendto(str(choose_message).encode(),
                                                       self.client_socket[self.now_player])
                                    choose_message = {"message": "player_change_active", "change_from": oppose.characters.index(change_from),
                                                      "change_to": oppose.characters.index(change_to)}
                                    self.socket.sendto(str(choose_message).encode(),
                                                       self.client_socket[~self.now_player])
                                    clear_skill_message = {"message": "clear_skill"}
                                    self.socket.sendto(str(clear_skill_message).encode(),
                                                       self.client_socket[~self.now_player])
                                    active = oppose.get_active_character_obj()
                                    skill = active.get_skills_type()
                                    init_skill_message = {"message": "init_skill", "skills": skill}
                                    self.socket.sendto(str(init_skill_message).encode(),
                                                       self.client_socket[self.now_player])
                                    self.handle_extra_effect("change", change_action_effect)
                            elif effect_obj == "ALL":
                                change_from = player.get_active_character_obj()
                                player.auto_change_active(extra_effect["CHANGE_CHARACTER"])
                                change_to = player.get_active_character_obj()
                                if change_from != change_to:
                                    change_action_effect = invoke_modify(self, "change", change_from,
                                                                         change_from=change_from,
                                                                         change_to=change_to, left_effect={"change_action": "fast"})
                                    choose_message = {"message": "player_change_active",
                                                      "change_from": player.characters.index(change_from),
                                                      "change_to": player.characters.index(change_to)}
                                    self.socket.sendto(str(choose_message).encode(),
                                                       self.client_socket[self.now_player])
                                    choose_message = {"message": "oppose_change_active",
                                                      "change_from": player.characters.index(change_from),
                                                      "change_to": player.characters.index(change_to)}
                                    self.socket.sendto(str(choose_message).encode(),
                                                       self.client_socket[~self.now_player])
                                    clear_skill_message = {"message": "clear_skill"}
                                    self.socket.sendto(str(clear_skill_message).encode(),
                                                       self.client_socket[self.now_player])
                                    active = player.get_active_character_obj()
                                    skill = active.get_skills_type()
                                    init_skill_message = {"message": "init_skill", "skills": skill}
                                    self.socket.sendto(str(init_skill_message).encode(),
                                                       self.client_socket[self.now_player])
                                    self.handle_extra_effect("change", change_action_effect)
                        if "HEAL" in extra_effect:
                            heal = extra_effect["HEAL"]
                            if effect_obj == "ACTIVE" or effect_obj == "SELF":
                                player.get_active_character_obj().change_hp(heal)
                                change_hp_message = {"message": "change_hp",
                                                     "position": player.current_character,
                                                     "hp": player.get_active_character_obj().get_hp()}
                                self.socket.sendto(str(change_hp_message).encode(),
                                                   self.client_socket[self.now_player])
                                change_hp_message = {"message": "oppose_change_hp",
                                                     "position": player.current_character,
                                                     "hp": player.get_active_character_obj().get_hp()}
                                self.socket.sendto(str(change_hp_message).encode(), self.client_socket[~self.now_player])
                            elif effect_obj == "STANDBY":
                                standby = player.get_standby_obj()
                                for obj in standby:
                                    obj.change_hp(heal)
                                    change_hp_message = {"message": "change_hp",
                                                         "position": player.characters.index(obj),
                                                         "hp": obj.get_hp()}
                                    self.socket.sendto(str(change_hp_message).encode(),
                                                       self.client_socket[~self.now_player])
                                    change_hp_message = {"message": "oppose_change_hp",
                                                         "position": player.characters.index(obj),
                                                         "hp": obj.get_hp()}
                                    self.socket.sendto(str(change_hp_message).encode(),
                                                       self.client_socket[self.now_player])
                            elif isinstance(effect_obj, Character):
                                effect_obj.change_hp(heal)
                                change_hp_message = {"message": "change_hp",
                                                     "position": player.characters.index(effect_obj),
                                                     "hp": effect_obj.get_hp()}
                                self.socket.sendto(str(change_hp_message).encode(),
                                                   self.client_socket[self.now_player])
                                change_hp_message = {"message": "oppose_change_hp",
                                                     "position": player.characters.index(effect_obj),
                                                     "hp": effect_obj.get_hp()}
                                self.socket.sendto(str(change_hp_message).encode(),
                                                   self.client_socket[~self.now_player])
                            elif effect_obj == "ALL":
                                characters = player.characters
                                for index, character in enumerate(characters):
                                    character.change_hp(heal)
                                    change_hp_message = {"message": "change_hp",
                                                         "position": index,
                                                         "hp": character.get_hp()}
                                    self.socket.sendto(str(change_hp_message).encode(),
                                                       self.client_socket[self.now_player])
                                    change_hp_message = {"message": "oppose_change_hp",
                                                         "position": index,
                                                         "hp": character.get_hp()}
                                    self.socket.sendto(str(change_hp_message).encode(),
                                                       self.client_socket[~self.now_player])
                        if "APPLICATION" in extra_effect:
                            element = extra_effect["APPLICATION"]
                            print("self_application", player.get_active_character_obj().name)
                            if effect_obj == "ACTIVE":
                                self.handle_element_reaction(player.get_active_character_obj(), element, "self")
                        if "CHANGE_ENERGY" in extra_effect:
                            if effect_obj == "ACTIVE":
                                active = player.get_active_character_obj()
                                active.change_energy(extra_effect["CHANGE_ENERGY"])
                                char_index = player.characters.index(active)  # 被动技能， 不为出战角色
                                energy = (active.get_energy(), active.max_energy)
                                change_energy_message = {"message": "change_energy", "position": char_index,
                                                         "energy": energy}
                                self.socket.sendto(str(change_energy_message).encode(),
                                                   self.client_socket[self.players.index(player)])
                                change_energy_message = {"message": "oppose_change_energy", "position": char_index,
                                                         "energy": energy}
                                self.socket.sendto(str(change_energy_message).encode(),
                                                   self.client_socket[~self.players.index(player)])
            elif effect_type == "REROLL":
                if isinstance(effect_value, int):
                    for _ in range(effect_value):
                        self.ask_player_reroll_dice(player)
            elif effect_type == "extra_attack":
                for key, value in effect_value.items():
                    self.handle_damage(None, "team", {key: value})
            elif effect_type == "attack_all":
                active = oppose.get_active_character_obj()
                standby = oppose.get_standby_obj()
                for key, value in effect_value.items():
                    self.handle_damage(None, active, {key: value})
                    for each in standby:
                        self.handle_damage(None, each, {key:value})
            elif effect_type == "CHANGE_ACTION":
                if operation == "change":
                    left_effect.update({effect_type: effect_value})
            elif effect_type == "DMG":
                if operation == "use_skill" or operation == "infusion":
                    left_effect.update({effect_type: effect_value})
        return left_effect

    def round_end_consume_modify(self):
        for player in self.players:
            need_remove_modifies = DuplicateDict()  # consume需要传原始modify，但循环时禁止改变原始modify， 故只能统一移除
            for character in player.characters:
                for modify_name, modify in character.modifies.items():
                    consume_state = consume_modify_usage(modify, "end")
                    if consume_state == "remove":
                        need_remove_modifies.update({modify_name: character.modifies})
            for modify_name, modify in player.team_modifier.items():
                consume_state = consume_modify_usage(modify, "end")
                if consume_state == "remove":
                    need_remove_modifies.update({modify_name: player.team_modifier})
            for summon in player.summons:
                for modify_name, modify in summon.modifies.items():
                    consume_state = consume_modify_usage(modify, "end")
                    if consume_state == "remove":
                        need_remove_modifies.update({modify_name: summon.modifies})
            for support in player.supports:
                for modify_name, modify in support.modifies.items():
                    consume_state = consume_modify_usage(modify, "end")
                    if consume_state == "remove":
                        need_remove_modifies.update({modify_name: support.modifies})
            for modify_name, obj in need_remove_modifies.items():
                if modify_name in obj:
                    obj.pop(modify_name)



# if __name__ == '__main__':
#     mode = "Game1"
#     state = pre_check(mode)
#     if isinstance(state, list):
#         error = " ".join(state)
#         print("以下卡牌不合法：%s" % error)
#     else:
#         game = Game(mode)
#         game.start_game()
