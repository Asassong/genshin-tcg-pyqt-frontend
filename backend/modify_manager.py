# Genius Invokation TCG, write in python.
# Copyright (C) 2023 Asassong


"""
                                                                                             |<------------------------------------------|
(GAME_START)->(INIT_DRAW)->||: START/STAGE->ROLL->ACTION-> USE_SKILL/COST->INFUSION->ATTACK/COMBAT/ANY_ATTACK->DEFENSE/COMBAT->SHIELD->EXTRA_ATTACK->AFTER_ATTACK ->END/STAGE->DRAW :||->(GAME_END)
                                                           USE_SKILL/COST->PIERCE/ANY_ATTACK->DEF_PIERCE->EXTRA_ATTACK->AFTER_ATTACK
                                                           CHANGE_COST/COST->CHANGE->AFTER_CHANGE
                                                           CARD_COST/COST->PLAY_CARD

DRAW      DRAW_NUM
          DRAW_TIMES

ROLL      ROLL_TIMES
          FIXED_DICE
          ROLL_NUM

DICE      REMOVE_DICE
          APPEND_DICE

CARD      APPEND_CARD
          DRAW_CARD
          REMOVE_CARD

SUPPORT   ADD_SUPPORT
          REMOVE_SUPPORT

SUMMON    ADD_SUMMON
          REMOVE_SUMMON

CHANGE_COST

CHANGE    CHANGE_ACTION

ACTION    USE_SKILL

USE_SKILL SKILL_COST
          ADD_ENERGY
          COUNTER

INFUSION

COMBAT    ATTACK    DMG
          DEFENSE   HURT

SHIELD

EXTRA_ATTACK CREATE_DMG

AFTER_ATTACK HEAL

STAGE     END
"""
from player import Player
from character import Character
from card import Card
from summon import Summon
from enums import EffectObj, TimeLimit, WeaponType, ElementType
# from game import Game
from typing import Optional, Union
from utils import DuplicateDict



def add_modify(game, invoker: Union[Character, Card, Summon], modify: list, modify_name: str, force=False):
    player = game.get_now_player()
    oppose = game.get_oppose()
    for index, each in enumerate(modify):
        if "IMMEDIATE" in each["time_limit"]:
            immediate_effect = invoke_modify(game, "none", invoker, modify={modify_name + "_" + str(index): each})
            game.handle_extra_effect("none", immediate_effect)
        else:
            effect_obj = each["effect_obj"]
            if EffectObj[effect_obj] == EffectObj.SELF:
                append_modify(invoker.modifies, (modify_name + "_" + str(index), each), force)
            elif EffectObj[effect_obj] == EffectObj.NO_SELF:
                others = player.get_no_self_obj(invoker)
                for other in others:
                    append_modify(other.modifies, (modify_name + "_" + str(index), each), force)
            elif EffectObj[effect_obj] == EffectObj.OPPOSE_SELF:
                oppose_active = oppose.get_active_character_obj()
                append_modify(oppose_active.modifies, (modify_name + "_" + str(index), each), force)
            elif EffectObj[effect_obj] == EffectObj.NO_OPPOSE_SELF:
                others = oppose.get_no_self_obj(invoker)
                for other in others:
                    append_modify(other.modifies, (modify_name + "_" + str(index), each), force)
            elif EffectObj[effect_obj] == EffectObj.OPPOSE_ACTIVE:
                append_modify(oppose.team_modifier, (modify_name + "_" + str(index), each), force)
            else:
                append_modify(player.team_modifier, (modify_name + "_" + str(index), each), force)


def append_modify(old_modify: DuplicateDict, new_modify: tuple[str, dict], force=False):
    # need_del_index = None
    # stack_count = []
    modify_name = new_modify[0]
    # for index, old_modify_name in enumerate(old_modify):
    if modify_name in old_modify:
        # if modify_name == old_modify_name:
        if not force:
            if "stack" in new_modify[1]:
                while True:
                    stack_count = old_modify.count(modify_name)
                    if stack_count >= new_modify[1]["stack"]:
                        old_modify.pop(modify_name)
                    else:
                        break
            else:
                while True:
                    if modify_name in old_modify:
                        old_modify.pop(modify_name)
                    else:
                        break
    #             need_del_index = index
    # if stack_count:
    #     if len(stack_count) >= new_modify[1]["stack"]:
    #         need_del_index = stack_count[0]
    # modify = new_modify[1].copy()
    old_modify.update({modify_name: new_modify[1]})
    # if need_del_index is not None:
    #     old_modify.pop(need_del_index)


def invoke_modify(game, operation: str, invoker: Union[Character, Summon, Card, None], player: Player=None, use: bool=True, **kwargs):
    if player is not None:
        oppose: list = game.players.copy()
        oppose.remove(player)
        oppose = oppose[0]
    else:
        player = game.get_now_player()
        oppose: Player = game.get_oppose()
    all_related_modifies = DuplicateDict()
    if "modify" in kwargs:
        all_related_modifies.update(kwargs["modify"])
    modify_belong = {}
    if operation == "defense" or operation == "shield":
        oppose_active = oppose.get_active_character_obj()
        for modify_name, modify_info in oppose_active.modifies.items():
            if invoke_relate(operation, modify_info):
                all_related_modifies.update({modify_name: modify_info})
                modify_belong[modify_name] = oppose_active.modifies
        for modify_name, modify_info in oppose.team_modifier.items():
            if invoke_relate(operation, modify_info):
                all_related_modifies.update({modify_name: modify_info})
                modify_belong[modify_name] = oppose.team_modifier
        oppose_summons = oppose.summons
        for summon in oppose_summons:
            for modify_name, modify_info in summon.modifies.items():
                if invoke_relate(operation, modify_info):
                    all_related_modifies.update({modify_name: modify_info})
                    modify_belong[modify_name] = summon.modifies
        oppose_support = oppose.supports
        for support in oppose_support:
            for modify_name, modify_info in support.modifies.items():
                if invoke_relate(operation, modify_info):
                    all_related_modifies.update({modify_name: modify_info})
                    modify_belong[modify_name] = support.modifies
    elif operation == "none":
        pass  # ??????????????? ?????????????????????modify
    elif operation == "start":
        for modify_name, modify_info in invoker.modifies.items():
            print("start_modify", modify_info)
            if invoke_relate("start", modify_info):
                all_related_modifies.update({modify_name: modify_info})
                modify_belong[modify_name] = invoker.modifies
    elif operation == "end":
        for modify_name, modify_info in invoker.modifies.items():
            if invoke_relate("end", modify_info):
                all_related_modifies.update({modify_name: modify_info})
                modify_belong[modify_name] = invoker.modifies
    elif operation == "team_end":
        for modify_name, modify_info in player.team_modifier.items():
            if invoke_relate("end", modify_info):
                all_related_modifies.update({modify_name: modify_info})
                modify_belong[modify_name] = player.team_modifier
    elif operation == "team_start":
        for modify_name, modify_info in player.team_modifier.items():
            if invoke_relate("start", modify_info):
                all_related_modifies.update({modify_name: modify_info})
                modify_belong[modify_name] = player.team_modifier
    else:
        if invoker is not None:
            for modify_name, modify_info in invoker.modifies.items():
                if invoke_relate(operation, modify_info):
                    all_related_modifies.update({modify_name: modify_info})
                    modify_belong[modify_name] = invoker.modifies
        if operation == "change_cost" or operation == "change":
            for modify_name, modify_info in kwargs["change_to"].modifies.items():
                if invoke_relate(operation, modify_info):
                    all_related_modifies.update({modify_name: modify_info})
                    modify_belong[modify_name] = kwargs["change_to"].modifies
        for modify_name, modify_info in player.team_modifier.items():
            if invoke_relate(operation, modify_info):
                all_related_modifies.update({modify_name: modify_info})
                modify_belong[modify_name] = player.team_modifier
        summons = player.summons
        for summon in summons:
            for modify_name, modify_info in summon.modifies.items():
                if invoke_relate(operation, modify_info):
                    all_related_modifies.update({modify_name: modify_info})
                    modify_belong[modify_name] = summon.modifies
        supports = player.supports
        for support in supports:
            for modify_name, modify_info in support.modifies.items():
                if invoke_relate(operation, modify_info):
                    all_related_modifies.update({modify_name: modify_info})
                    modify_belong[modify_name] = support.modifies
    """
    if operation == "draw": # game -> effect, draw???????????????
    elif operation == "start":  # game -> effect
    elif operation == "roll":  # game -> FIXED_DICE, REROLL
    elif operation == "action": # game -> USE_SKILL, effect
    elif operation == "use_skill":  # SKILL_NAME, SKILL_TYPE, skill_cost, add_energy, game -> skill_cost, add_energy
    elif operation == "change_cost": # CHANGE_COST, change_from, change_to, game -> CHANGE_COST
    elif operation == "card_cost":  # card_cost, game -> card_cost
    elif operation == "infusion":  # SKILL_NAME, SKILL_TYPE, game -> infusion
    elif operation == "attack":  # SKILL_NAME, SKILL_TYPE, damage, element, reaction, game -> damage
    elif operation == "defense": # SKILL_TYPE, hurt, element, reaction, game -> hurt
    elif operation == "shield": # hurt, game -> hurt
    elif operation == "extra":  # game -> effect
    elif operation == "play_card":  # CARD_TAG, game -> effect
    elif operation == "change":  # game, change_from, change_to -> change_action
    elif operation == "end":  # game -> effect
    """
    need_remove_modifies = {}
    left_effect = {"extra_effect":[]}
    if "left_effect" in kwargs:
        left_effect.update(kwargs["left_effect"])
    special_effect = {}
    had_invoked_modify = []
    exclusive_modify = []
    if all_related_modifies:
        print("relate_modify", all_related_modifies.to_list())
    for modify_name, modify in all_related_modifies.items():
        if modify_name in had_invoked_modify:
            if "repeated" not in modify:
                continue
            else:
                if modify["repeated"] == "False":
                    continue
        condition = modify["condition"]
        satisfy_condition = check_condition(condition, game, **kwargs, invoke=invoker)
        special = []
        if satisfy_condition:
            special = satisfy_condition[1]
            time_limit = modify["time_limit"]
            for limit_type, limit in time_limit.items():
                if TimeLimit[limit_type] == TimeLimit.ROUND:
                    left_usage = time_limit[limit_type][1]
                    if left_usage <= 0:
                        satisfy_condition = False
                        break
                elif TimeLimit[limit_type] == TimeLimit.PREPARE:
                    prepare = time_limit[limit_type]
                    if prepare[0] != prepare[1]:
                        satisfy_condition = False
                if TimeLimit[limit_type] == TimeLimit.USAGE:  # DuplicatedDict???????????????????????????
                    if time_limit[limit_type] <= 0:
                        satisfy_condition = False
        real_invoker = invoker
        if "EXCLUSIVE" in special:
            super_modify_name = modify_name.rsplit("_", 1)[0]
            if super_modify_name in exclusive_modify:
                satisfy_condition = False
            else:
                exclusive_modify.append(super_modify_name)
        if "NEED_REMOVE" in special:
            if "REMOVE" not in special:
                satisfy_condition = False
            need_remove_modifies[modify_name] = real_invoker
        if satisfy_condition:
            effect_obj = modify["effect_obj"]
            consume = False
            if isinstance(effect_obj, str):
                effect = modify["effect"]
                print("effect", effect)
                if EffectObj[effect_obj] == EffectObj.COUNTER:
                    for counter_name, counter_change in effect.items():
                        if isinstance(counter_change, str):
                            if counter_name in real_invoker.counter:
                                real_invoker.counter[counter_name] += eval(counter_change)
                        else:
                            if counter_name in real_invoker.counter:
                                real_invoker.counter[counter_name] = counter_change
                        # if isinstance(real_invoker, Card):
                        #     index = player.supports.index(real_invoker)
                        #     change_count_message = {"message": "change_support_count", "support_index": index, "count": str(real_invoker.counter[counter_name])}
                        #     game.socket.sendto(str(change_count_message).encode(), game.client_socket[game.players.index(player)])
                        #     change_count_message = {"message": "change_oppose_support_count", "support_index": index, "count": str(real_invoker.counter[counter_name])}
                        #     game.socket.sendto(str(change_count_message).encode(),
                        #                        game.client_socket[~game.players.index(player)])
                    consume |= True
                else:
                    for effect_type, effect_value in effect.items():
                        if effect_type == "REROLL":  # ???????????????????????????1???"+1"?????????????????????????????????????????????????????????????????????
                            if effect_type in left_effect:
                                if isinstance(effect_value, str):
                                    left_effect[effect_type] = "+" + str(eval(str(left_effect[effect_type]) + effect_value))
                                else:
                                    left_effect[effect_type] += effect_value
                            else:
                                left_effect.update({effect_type: effect_value})
                            consume |= True
                        elif effect_type == "FIXED_DICE":
                            if effect_type in left_effect:
                                left_effect[effect_type] += effect_value
                            else:
                                left_effect.update({effect_type: effect_value})
                            consume |= True
                        elif effect_type == "USE_SKILL":  # ????????????????????????????????????
                            left_effect.update({effect_type: effect_value})
                            consume |= True
                        elif effect_type == "CHANGE_COST":
                            if "cost" in kwargs:
                                cost = kwargs["cost"]
                                if "ANY" in cost:
                                    if cost["ANY"] != 0:
                                        cost["ANY"] += eval(effect_value)
                                        consume |= True
                                    else:
                                        if eval(effect_value) > 0:
                                            cost["ANY"] += eval(effect_value)
                                            consume |= True
                        elif effect_type == "CHANGE_ACTION": #  change?????????????????????
                            if "change_action" not in left_effect:
                                left_effect["change_action"] = "fast"
                                consume |= True
                        elif effect_type == "SKILL_ADD_ENERGY":
                            if "add_energy" in kwargs:
                                left_effect["add_energy"] = kwargs["add_energy"]
                                consume |= True
                        elif effect_type in ["COST_ANY", "COST_PYRO", "COST_HYDRO", "COST_ELECTRO", "COST_CRYO", "COST_DENDRO", "COST_ANEMO", "COST_GEO", "COST_ALL", "COST_ELEMENT"]:
                            if "cost" in kwargs:
                                cost: dict = kwargs["cost"]
                                element_type = effect_type.replace("COST_", "")
                                if element_type in ElementType.__members__:
                                    if element_type in cost:
                                        cost[element_type] += eval(effect_value)
                                        if cost[element_type] <= 0:
                                            cost.pop(element_type)
                                            consume |= True
                                elif element_type == "ANY":
                                    if element_type in cost:
                                        cost[element_type] += eval(effect_value)
                                        if cost[element_type] <= 0:
                                            cost.pop(element_type)
                                            consume |= True
                                elif element_type == "ELEMENT":
                                    consume |= False
                                    for element in ['CRYO', 'HYDRO', 'PYRO', 'ELECTRO', 'GEO', 'DENDRO', 'ANEMO']:
                                        if element in cost:
                                            cost[element] += eval(effect_value)
                                            consume |= True
                                            if cost[element] <= 0:
                                                cost.pop(element)
                                            break
                                elif element_type == "ALL": # ????????????same
                                    if "SAME" in cost:
                                        cost["SAME"] += eval(effect_value)
                                        if cost["SAME"] <= 0:
                                            cost.pop("SAME")
                                            consume |= True
                        elif effect_type == "DMG":
                            if "{NUMBER}" in effect_value: # ??????NUMBER???
                                for each_special in special:
                                    if isinstance(each_special, dict):
                                        if "NUMBER" in each_special:
                                            effect_value = effect_value.format(NUMBER=each_special["NUMBER"])
                                            break
                            if "damage" in kwargs:
                                if effect_value.startswith("*") or effect_value.startswith("/"):
                                    special_effect["damage"] = effect_value
                                else:
                                    kwargs["damage"] += eval(effect_value)
                                consume |= True
                        elif effect_type == "HURT":
                            if "hurt" in kwargs:
                                if effect_value.startswith("*") or effect_value.startswith("/"):
                                    special_effect["hurt"] = effect_value
                                    consume |= True
                                else:
                                    if kwargs["hurt"] > 0:
                                        kwargs["hurt"] += eval(effect_value)
                                        consume |= True
                        elif effect_type == "SHIELD":
                            if "hurt" in kwargs:
                                if kwargs["hurt"] > 0:
                                    if kwargs["hurt"] >= effect_value:
                                        kwargs["hurt"] -= effect_value
                                        need_remove_modifies[modify_name] = real_invoker
                                    else:
                                        effect["SHIELD"] -= kwargs["hurt"]
                                        kwargs["hurt"] = 0
                                    consume |= True
                        elif effect_type == "INFUSION":
                            if "infusion" not in left_effect:
                                left_effect["infusion"] = effect_value
                                consume |= True
                        elif effect_type == "ADD_MODIFY":
                            consume |= True
                            if use:  # ??????????????????????????????
                                if consume:
                                    had_invoked_modify.append(modify_name)
                                    use_state = consume_modify_usage(modify)
                                    if use_state == "remove":
                                        modify_belong[modify_name].pop(modify_name)
                                        # need_remove_modifies[modify_name] = real_invoker
                            if isinstance(effect_value, list):
                                add_modify(game, real_invoker, effect_value, modify_name + "_inner")
                            else:
                                add_modify(game, real_invoker, [effect_value], modify_name + "_inner")
                            use = False
                        elif effect_type in ["HYDRO_DMG", "GEO_DMG", "ELECTRO_DMG","DENDRO_DMG", "PYRO_DMG", "PHYSICAL_DMG",
                                    "CRYO_DMG", "ANEMO_DMG", "PIERCE_DMG"]:
                            attack_type = effect_type.replace("_DMG", "")
                            if "extra_attack" not in left_effect:
                                left_effect["extra_attack"] = DuplicateDict()
                            if effect_obj == "OPPOSE_ALL":
                                left_effect["attack_all"] = DuplicateDict()
                                left_effect["attack_all"].update({attack_type: effect_value})
                            else:
                                left_effect["extra_attack"].update({attack_type: effect_value})
                        else:
                            if effect_obj == "SELF":
                                left_effect["extra_effect"].append(({effect_type: effect_value}, invoker))
                            else:
                                left_effect["extra_effect"].append(({effect_type: effect_value}, effect_obj))
                            consume |= True
            if use:
                if consume:
                    had_invoked_modify.append(modify_name)
                    use_state = consume_modify_usage(modify)
                    if use_state == "remove":
                        modify_belong[modify_name].pop(modify_name)
                        # need_remove_modifies[modify_name] = real_invoker
    if "cost" in kwargs:
        left_effect["cost"] = kwargs["cost"]
    if "damage" in kwargs:
        if "damage" in special_effect:
            kwargs["damage"] = eval(str(kwargs["damage"]) + special_effect["damage"])
        left_effect["damage"] = -(-kwargs["damage"]//1) # ceil
    if "hurt" in kwargs:
        kwargs["hurt"] = max(kwargs["hurt"], 0)
        if "hurt" in special_effect:
            kwargs["hurt"] = eval(str(kwargs["hurt"]) + special_effect["hurt"])
        left_effect["hurt"] = -(-kwargs["hurt"]//1)  # ceil
    # for need_remove_modify, modify_on in need_remove_modifies.items():
    #     remove_modify(modify_belong[need_remove_modify], need_remove_modify)
    return left_effect

def invoke_relate(operation, modify):
    modify_tag = modify["category"]
    if modify_tag == "any":
        return True
    else:
        if operation == "draw":
            if modify_tag in ["draw"]:
                return True
        elif operation == "start":
            if modify_tag in ["stage", "start"]:
                return True
        elif operation == "roll":
            if modify_tag in ["roll"]:
                return True
        elif operation == "action":
            if modify_tag in ["action"]:
                return True
        elif operation == "use_skill":
            if modify_tag in ["use_skill", "cost"]:
                return True
        elif operation == "change_cost":
            if modify_tag in ["change_cost", "cost"]:
                return True
        elif operation == "card_cost":
            if modify_tag in ["card_cost", "cost"]:
                return True
        elif operation == "infusion":
            if modify_tag in ["infusion"]:
                return True
        elif operation == "attack":
            if modify_tag in ["attack", "combat"]:
                return True
        elif operation == "defense":
            if modify_tag in ["defense", "combat"]:
                return True
        elif operation == "shield":
            if modify_tag in ["shield"]:
                return True
        elif operation == "extra_attack":
            if modify_tag in ["extra_attack"]:
                return True
        elif operation == "after_attack":
            if modify_tag in ["after_attack"]:
                return True
        elif operation == "play_card":
            if modify_tag in ["play_card"]:
                return True
        elif operation == "change":
            if modify_tag in ["change"]:
                return True
        elif operation == "end":
            if modify_tag in ["stage", "end"]:
                return True
    return False

def remove_modify(obj: DuplicateDict, modify_name: str, name_level="special"):
    if name_level == "special":
        obj.pop(modify_name)
    elif name_level == "main":
        name_list = []
        for each_name, _ in obj.items():
            main_name, other = each_name.split("_", 1)
            if modify_name == main_name:
                name_list.append(each_name)
        for need_remove in name_list:
            obj.pop(need_remove)

def check_condition(condition, game, **kwargs):
    special = []
    if condition:
        for each in condition:
            if isinstance(each, str):
                if each.startswith("STAGE_"):
                    condition_stage = each.replace("STAGE_", "")
                    if condition_stage == game.stage.name:
                        continue
                    else:
                        return False
                elif each == "BE_CHANGED_AS_ACTIVE":
                    if "change_to" in kwargs:
                        if kwargs["change_to"] == kwargs["invoke"]:
                            continue
                        else:
                            return False
                    else:
                        return False
                elif each == "CHANGE_TO_STANDBY" or each == "CHANGE_AVATAR":
                    if "change_from" in kwargs:
                        if kwargs["change_from"] == kwargs["invoke"]:
                            print(kwargs["change_from"].name, kwargs["invoke"].name)
                            continue
                        else:
                            return False
                    else:
                        return False
                elif each == "EXCLUSIVE":
                    if "exclusive" in kwargs:
                        return False
                    else:
                        special.append("EXCLUSIVE")
                        continue
                elif each == "BEING_HIT":
                    if "hurt" in kwargs:
                        continue
                    else:
                        return False
                elif each == "SKILL":
                    if "skill_type" in kwargs:
                        continue
                    else:
                        return False
                elif each == "NORMAL_ATTACK":
                    if "skill_type" in kwargs:
                        if "Normal Attack" in kwargs["skill_type"]:
                            continue
                        else:
                            return False
                    else:
                        return False
                elif each == "ELEMENTAL_SKILL":
                    if "skill_type" in kwargs:
                        if "Elemental Skill" in kwargs["skill_type"]:
                            continue
                        else:
                            return False
                    else:
                        return False
                elif each == "ELEMENTAL_BURST":
                    if "skill_type" in kwargs:
                        if "Elemental Burst" in kwargs["skill_type"]:
                            continue
                        else:
                            return False
                    else:
                        return False
                elif each == "ELEMENT_DMG":
                    if "damage" in kwargs and "element" in kwargs:
                        if kwargs["element"] != "PHYSICAL" and kwargs["element"] != "PIERCE":
                            continue
                        else:
                            return False
                    else:
                        return False
                elif each == "ELEMENT_HURT":
                    if "hurt" in kwargs and "element" in kwargs:
                        if kwargs["element"] != "PHYSICAL" and kwargs["element"] != "PIERCE":
                            continue
                        else:
                            return False
                    else:
                        return False
                elif each == "ELEMENT_REACTION":
                    if "reaction" in kwargs:
                        if kwargs["reaction"] is not None:
                            continue
                        else:
                            return False
                    else:
                        return False
                elif each == "SELF_HURT":
                    special.append("SELF_HURT")
                elif each == "SWIRL":
                    if "reaction" in kwargs:
                        if kwargs["reaction"] == "SWIRL":
                            continue
                        else:
                            return False
                elif each == "IS_ACTIVE":
                    if game.get_now_player().get_active_character_obj() == kwargs["invoke"]:
                        continue
                    else:
                        return False
                elif each == "IS_NOT_ACTIVE":
                    if game.get_now_player().get_active_character_obj() != kwargs["invoke"]:
                        continue
                    else:
                        return False
                elif each == "GET_MOST_HURT":
                    special.append({"OBJ": game.get_now_player().get_most_hurt()})
                elif each == "PYRO_RELATED":
                    if "reaction" in kwargs:
                        if kwargs["reaction"] in ["MELT", "VAPORIZE", "OVERLOADED", "BURNING"]:
                            continue
                        elif kwargs["reaction"] == "SWIRL":
                            if kwargs["swirl_element"] == "PYRO":
                                continue
                            else:
                                return False
                        elif kwargs["reaction"] == "CRYSTALLIZE":
                            if kwargs["crystallize_element"] == "PYRO":
                                continue
                            else:
                                return False
                        else:
                            return False
                elif each == "HYDRO_RELATED":
                    if "reaction" in kwargs:
                        if kwargs["reaction"] in ["VAPORIZE", "FROZEN", "ELECTRO_CHARGE", "BLOOM"]:
                            continue
                        elif kwargs["reaction"] == "SWIRL":
                            if kwargs["swirl_element"] == "HYDRO":
                                continue
                            else:
                                return False
                        elif kwargs["reaction"] == "CRYSTALLIZE":
                            if kwargs["crystallize_element"] == "HYDRO":
                                continue
                            else:
                                return False
                        else:
                            return False
                elif each == "ELECTRO_RELATED":
                    if "reaction" in kwargs:
                        if kwargs["reaction"] in ["OVERLOADED", "SUPER_CONDUCT", "ELECTRO_CHARGE", "CATALYZE"]:
                            continue
                        elif kwargs["reaction"] == "SWIRL":
                            if kwargs["swirl_element"] == "ELECTRO":
                                continue
                            else:
                                return False
                        elif kwargs["reaction"] == "CRYSTALLIZE":
                            if kwargs["crystallize_element"] == "ELECTRO":
                                continue
                            else:
                                return False
                        else:
                            return False
                elif each == "CRYO_RELATED":
                    if "reaction" in kwargs:
                        if kwargs["reaction"] in ["MELT", "SUPER_CONDUCT", "FROZEN", "SUPER_CONDUCT"]:
                            continue
                        elif kwargs["reaction"] == "SWIRL":
                            if kwargs["swirl_element"] == "CRYO":
                                continue
                            else:
                                return False
                        elif kwargs["reaction"] == "CRYSTALLIZE":
                            if kwargs["crystallize_element"] == "CRYO":
                                continue
                            else:
                                return False
                        else:
                            return False
                elif each == "DENDRO_RELATED":
                    if "reaction" in kwargs:
                        if kwargs["reaction"] in ["BURNING", "BLOOM", "CATALYZE"]:
                            continue
                        else:
                            return False
                elif each == "ANEMO_RELATED":
                    if "reaction" in kwargs:
                        if kwargs["reaction"] == "SWIRL":
                            continue
                        else:
                            return False
                elif each == "GEO_RELATED":
                    if "reaction" in kwargs:
                        if kwargs["reaction"] == "CRYSTALLIZE":
                            continue
                        else:
                            return False
                elif each == "FORCE":
                    special.append("FORCE")
                elif each == "HAVE_SHIELD":
                    pass
                elif each == "REMOVE":
                    if "NEED_REMOVE" not in special:
                        return False
                    else:
                        special.append("REMOVE")
                elif each == "REPLACE":
                    # TODO
                    pass
                elif each == "DIFFERENCE_FIRST":
                    # TODO
                    pass
                elif each == "OPPOSE_DIE":
                    pass
                else:
                    return False
            elif isinstance(each, list):
                if each[0] == "CHECK":
                    satisfy = False
                    for or_ in each[1:]:
                        type_, attribute, compare = or_.split("_", 2)
                        if type_ == "COUNTER":
                            if kwargs["invoke"] is not None:
                                if attribute in kwargs["invoke"].counter:
                                    num = kwargs["invoke"].counter[attribute]
                                    if eval(str(num) + compare):
                                        satisfy = True
                                        break
                        elif type_ == "ELEMENT":
                            if attribute == "HURT":
                                if "hurt" in kwargs and "element" in kwargs:
                                    if kwargs["element"] == compare:
                                        satisfy = True
                                        break
                                    elif compare == "ELEMENT":
                                        if kwargs["element"] != "PHYSICAL" or kwargs["element"] != "PIERCE":
                                            satisfy = True
                                            break
                            elif attribute == "ATTACK":
                                if "damage" in kwargs and "element" in kwargs:
                                    if kwargs["element"] == compare:
                                        satisfy = True
                                        break
                                    elif compare == "ELEMENT":
                                        if kwargs["element"] != "PHYSICAL" or kwargs["element"] != "PIERCE":
                                            satisfy = True
                                            break
                            elif attribute == "SELF":
                                element = kwargs["invoke"].element
                                if element == compare:
                                    satisfy = True
                                    break
                        elif type_ == "WEAPON":
                            if attribute == "ACTIVE":
                                weapon = game.get_now_player().get_active_character_obj().weapon
                            else:
                                weapon = WeaponType.NONE
                            if compare == "MELEE":
                                if weapon.name in ["POLEARM", "SWORD", "CLAYMORE"]:
                                    satisfy = True
                                    break
                            else:
                                if weapon.name == compare:
                                    satisfy = True
                                    break
                        elif type_ == "HURT":
                            if "hurt" in kwargs:
                                if attribute == "ALL":
                                    if eval(str(kwargs["hurt"]) + compare):
                                        satisfy = True
                                        break
                                else:
                                    if "element" in kwargs:
                                        if attribute == kwargs["element"]:
                                            satisfy = True
                                            break
                        elif type_ == "HP":
                            if attribute == "ACTIVE":
                                hp = game.get_now_player().get_active_character_obj().get_hp()
                                if eval(str(hp) + compare):
                                    satisfy = True
                                    break
                            elif attribute == "OPPOSE":
                                hp = game.get_oppose().get_active_character_obj().get_hp()
                                if eval(str(hp) + compare):
                                    satisfy = True
                                    break
                        elif type_ == "DICE":
                            if attribute == "PLAYER":
                                dice_num = len(game.get_now_player().dices)
                                if eval(str(dice_num) + compare):
                                    satisfy = True
                                    break
                        elif type_ == "ENERGY":
                            if attribute == "NEW":
                                if "change_to" in kwargs:
                                    energy = kwargs["change_to"].energy
                                    if eval(str(energy) + compare):
                                        continue
                                    else:
                                        return False
                    if satisfy:
                        continue
                    else:
                        return False
                elif each[0] == "HAVE_CARD":
                    cards = game.get_now_player().hand_cards
                    if each[1] in cards:
                        continue
                    else:
                        return False
                elif each[0] == "DONT_HAVE_CARD":
                    cards = game.get_now_player().hand_cards
                    if each[1] in cards:
                        return False
                    else:
                        continue
                elif each[0] == "HAVE_STATE":
                    if each[1] == "SELF":
                        state_range = kwargs["invoke"].modifies
                    else:
                        state_range = game.get_now_player().team_modifier
                    satisfy = False
                    for each_state in state_range:
                        for state_name, _ in each_state.items():
                            exact_state_name = state_name.split("_", 1) # inner??????
                            if exact_state_name == each[2]:
                                satisfy = True
                                break
                        if satisfy:
                            break
                    if not satisfy:
                        return False
                elif each[0] == "HAVE_MODIFY":
                    if each[1] == "SELF":
                        state_range = kwargs["invoke"].modifies
                    else:
                        state_range = game.get_now_player().team_modifier
                    satisfy = False
                    for each_state in state_range:
                        if each[2] in each_state:
                            satisfy = True
                            break
                    if not satisfy:
                        return False
                elif each[0] == "HAVE_SUMMON":
                    summons = game.get_now_player().summons
                    if each[1] in summons:
                        continue
                    else:
                        return False
                elif each[0] == "SUM":
                    type_, attribute = each[1].split("_", 1)
                    if type_ == "SUMMON":
                        if attribute == "NUM":
                            special.append({"NUMBER": len(game.get_now_player().summons)})
                    elif type_ == "COUNTER":
                        if attribute in kwargs["invoke"].counter:
                            special.append({"NUMBER": kwargs["invoke"].counter[attribute]})
                    elif type_ == "NATION":
                        nation = game.get_now_player().get_character_nation()
                        special.append({"NUMBER": nation.count(attribute)})
                    elif type_ == "CARD":
                        if attribute == "COST":
                            card_cost = kwargs["card_cost"]
                            cost = 0
                            for key, value in card_cost.items():
                                cost += value
                            special.append({"NUMBER": cost})
                elif each[0] == "GET_ELEMENT":
                    if each[1] == "SWIRL":
                        if "swirl_element" in kwargs:
                            special.append({"ELEMENT": kwargs["swirl_element"]})
                        else:
                            return False
                    elif each[1] == "ACTIVE":
                        element = game.get_now_player().get_active_character_obj().element
                        special.append({"ELEMENT": element})
                    elif each[1] == "SELF":
                        element = kwargs["invoke"].element
                        special.append({"ELEMENT": element})
                    else:
                        return False
                elif each[0] == "EQUIP":
                    if "card_tag" in kwargs:
                        if each[1] in kwargs["card_tag"]:
                            continue
                        else:
                            return False
                    else:
                        return False
                elif each[0] == "PLAY_CARD":
                    if each[1].startswith("TYPE_"):
                        tag = each[1].replace("TYPE_", "")
                        if "card_tag" in kwargs:
                            if tag in kwargs["card_tag"]:
                                continue
                            else:
                                return False
                        else:
                            return False
                elif each[0] == "COMPARE":
                    two = [each[1], each[3]]
                    two_side = []
                    for each_side in two:
                        type_, attribute = each_side.split("_", 1)
                        if type_ == "SUMMON":
                            if attribute == "NUM":
                                two_side.append({"NUMBER": len(game.get_now_player().summons)})
                        elif type_ == "COUNTER":
                            if attribute in kwargs["invoke"].counter:
                                two_side.append({"NUMBER": kwargs["invoke"].counter[attribute]})
                        elif type_ == "NATION":
                            nation = game.get_now_player().get_character_nation()
                            two_side.append({"NUMBER": nation.count(attribute)})
                        elif type_ == "CARD":
                            if attribute == "COST":
                                card_cost = kwargs["card_cost"]
                                cost = 0
                                for key, value in card_cost.items():
                                    cost += value
                                two_side.append({"NUMBER": cost})
                        if eval(str(two_side[0]) + two[2] + str(two_side[1])):
                            continue
                        else:
                            return False
                elif each[0] == "USE_SKILL":
                    if "skill_name" in kwargs:
                        if kwargs["skill_name"] == each[1]:
                            continue
                        else:
                            return False
                    else:
                        return False
                elif each[0] == "OR":
                    satisfy = False
                    for or_condition in each[1:]:
                        condition_state = check_condition([or_condition], game, **kwargs)
                        if condition_state:
                            if condition_state[1]:
                                special += condition_state[1]
                            satisfy = True
                            break
                    if not satisfy:
                        return False
                elif each[0] == "NEED_REMOVE":
                    condition_state = check_condition([each[1]], game, **kwargs)
                    if not condition_state:
                        special.append("NEED_REMOVE")
    return True, special

def consume_modify_usage(modify, operation="use"):
    time_limit = modify["time_limit"]
    if operation == "use":
        if "USAGE" in time_limit:
            time_limit["USAGE"] -= 1
            if time_limit["USAGE"] <= 0:
                return "remove"
        if "ROUND" in time_limit:
            print("round_limit", time_limit["ROUND"])
            time_limit["ROUND"][1] -= 1
            print("round_limit", time_limit["ROUND"])
    elif operation == "end":
        if "ROUND" in time_limit:
            time_limit["ROUND"][1] = time_limit["ROUND"][0]
        if "DURATION" in time_limit:
            time_limit["DURATION"] -= 1
            if time_limit["DURATION"] == 0:
                return "remove"
    elif operation == "act":
        if "ACT" in time_limit:
            time_limit["ACT"] -= 1
            if time_limit["ACT"] == 0:
                return "remove"
        elif "PREPARE" in time_limit:
            prepare: list = time_limit["PREPARE"]
            prepare[0] += 1
            if prepare[0] > prepare[1]:
                return "remove"
    # print("consume_modify", modify)
    return None
