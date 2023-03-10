# Genius Invokation TCG, write in python.
# Copyright (C) 2023 Asassong


import json
from typing import Union, Any, Iterator
from collections.abc import MutableMapping
from collections import Counter


def read_json(file: str) -> dict[str]:
    with open(file, "r", encoding="utf-8") as f:
        text = json.load(f)
    return text


def pre_check(mode: str) -> Union[bool, list]:
    invalid = []
    config = read_json("config.json")
    character_dict = read_json("character.json")
    card_dict = read_json("card.json")
    game_config = config["Game"][mode]
    player_config = config["Player"]
    players = game_config["Player"]
    char_pack_limit = game_config["enable_character"]
    card_pack_limit = game_config["enable_deck"]
    enable_characters = {}
    for pack_name, pack in character_dict.items():
        if pack_name in char_pack_limit:
            enable_characters.update(pack)
    enable_cards = {}
    for pack_name, pack in card_dict.items():
        if pack_name in card_pack_limit:
            enable_cards.update(pack)
    for player in players:
        each_player_config = player_config[player]
        characters = each_player_config["character"]
        cards = each_player_config["card"]
        if len(characters) != each_player_config["character_num"]: # 这由game控制？
            invalid.append("角色卡数量不符合要求")
        if len(cards) != each_player_config["deck_num"]:
            invalid.append("牌组数量不符合要求")
        if len(set(characters)) != len(characters):
            invalid.append("禁止重复角色")
        character_elements = []
        for character in characters:
            if character in enable_characters:
                character_info = enable_characters[character]
                character_elements.append(character_info["element_type"])
            else:
                invalid.append("未知角色 %s" % character)
        count_card = dict(Counter(cards))
        for card_name, count in count_card.items():
            if count > 2:
                invalid.append("卡牌 %s 数量过多" % card_name)
            if card_name in enable_cards:
                card_info = enable_cards[card_name]
                if "deck_limit" in card_info:
                    deck_limit = card_info["deck_limit"]
                    if "character" in deck_limit:
                        if deck_limit["character"] not in characters:
                            invalid.append("卡牌 %s 不合法, 未携带对应角色" % card_name)
                    else:
                        for element in ["CRYO", "HYDRO", "PYRO", "ELECTRO", "DENDRO", "ANEMO", "GEO"]:
                            if element in deck_limit:
                                if character_elements.count(element) < deck_limit[element]:
                                    invalid.append("卡牌 %s 不合法, 对应元素角色不足" % card_name)
            else:
                invalid.append("未知卡牌 %s" % card_name)
    if invalid:
        return invalid
    return True

def update_or_append_dict(target_dict: dict, element:dict[Any, Union[int, float]]) -> None:
    for key, value in element.items():
        if key in target_dict:
            target_dict[key] += value
        else:
            target_dict.update({key: value})


class DuplicateDict(MutableMapping):  # setitem方法有问题
    def __init__(self, init: list[Union[dict, tuple]]=None):
        self._key_value_list = []
        if init is not None:
            for item in init:
                if isinstance(item, dict):
                    for key, value in item.items():
                        self._key_value_list.append((key, value))
                elif isinstance(item, tuple):
                    self._key_value_list.append(item)

    def __setitem__(self, key: Any, value: Any) -> None:
        self._key_value_list.append((key, value))

    def __delitem__(self, key: Any) -> None:
        pop_index = -1
        for index, item in enumerate(self._key_value_list):
            if item[0] == key:
                pop_index = index
                break
        if pop_index != -1: # 有抛异常的必要吗
            self._key_value_list.pop(pop_index)

    def __getitem__(self, key: Any) -> Any:
        for item in self._key_value_list:
            if item[0] == key:
                return item[1]

    def __len__(self) -> int:
        return len(self._key_value_list)

    def __iter__(self) -> Iterator:
        for item in self._key_value_list:
            yield item[0]

    def __contains__(self, key: Any) -> bool:
        if self.__getitem__(key) is not None:
            return True
        else:
            return False

    def index(self, key: Any) -> int:
        key_list = [item[0] for item in self._key_value_list]
        return key_list.index(key)

    def count(self, key:Any) -> int:
        key_list = [item[0] for item in self._key_value_list]
        return key_list.count(key)

    def enumerate(self) -> Iterator:
        for index, item in enumerate(self._key_value_list):
            yield index, item[0], item[1]

    def to_list(self) -> list[tuple]:
        return self._key_value_list

    def copy(self) -> "DuplicateDict":
        return DuplicateDict(self._key_value_list)

