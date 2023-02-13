# Genius Invokation TCG, write in python.
# Copyright (C) 2023 Asassong


from utils import read_json, DuplicateDict
from copy import deepcopy

class Card:
    def __init__(self, name, card_pack):
        self._name = name
        all_usable_card = {}
        for card_package, card in card_dict.items():
            if card_package in card_pack:
                all_usable_card.update(card)
        self.card_info = deepcopy(all_usable_card[name])
        self._cost = self.card_info["cost"]
        self.tag = self.card_info["tag"]
        self.effect_obj = self.card_info["effect_obj"]
        self.combat_limit = {}
        if "combat_limit" in self.card_info:
            self.combat_limit = self.card_info["combat_limit"]
        self.modifies = DuplicateDict()
        self.use_skill = ""
        if "use_skill" in self.card_info:
            self.use_skill = self.card_info["use_skill"]
        self.counter = {}
        if "counter" in self.card_info:
            self.counter = {counter: 0 for counter in self.card_info["counter"]}

    def get_name(self):
        return self._name

    def get_cost(self):
        return self._cost

    def init_modify(self):
        modifies = self.card_info["modify"]
        name = self.get_name()
        return modifies, name




card_dict = read_json("card.json")
