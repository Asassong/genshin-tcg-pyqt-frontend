# Genius Invokation TCG, write in python.
# Copyright (C) 2023 Asassong


from enums import ElementType, Nation
from utils import read_json, DuplicateDict


class Character:
    def __init__(self, character_name, character_package):
        all_usable_character = {}
        for pack_name, pack in character_info.items():
            if pack_name in character_package:
                all_usable_character.update(pack)
        character_detail = all_usable_character[character_name]
        self._hp = character_detail["hp"]
        self.max_hp = character_detail["hp"]
        self.max_energy = character_detail["energy"]
        self.name = character_name
        self.skills: dict = character_detail["skills"]
        self.element = ElementType[character_detail["element_type"].upper()]
        self.nation = [Nation[i] for i in character_detail["nation"] if i]
        self.weapon = character_detail["weapon"]
        if "counter" in character_detail:
            self.counter = {i: 0 for i in character_detail["counter"]}
        else:
            self.counter = {}
        self.alive = True
        self._energy = 0
        self.modifies = DuplicateDict()
        self.application: list[ElementType] = []  # 元素附着
        self.equipment = {"weapon": None, "artifact": None, "talent": None}  # 武器, 圣遗物, 天赋
        self._saturation = 0

    def change_hp(self, value):
        self._hp = min(self._hp + value, self.max_hp)
        if self._hp <= 0:
            self.alive = False
            self._hp = 0
            return "die"

    def get_hp(self):
        return self._hp

    def check_need_heal(self):  # 满血时有些卡牌不用触发治疗
        if self._hp == self.max_hp:
            return False
        else:
            return True

    def get_name(self):
        return self.name

    def get_card_info(self):
        detail = ""
        if self.alive:
            detail += "%s:血量%s 能量%s/%s" % (self.name, self._hp, self._energy, self.max_energy)
            detail += "附着" + self.application[0].name + " " if self.application else ""
            for key, value in self.equipment.items():
                if value is not None:
                    detail += " %s: %s," % (key, value)
            detail += "\n"
            return detail
        else:
            return "%s已退场\n" % self.name

    def get_skills_name(self) -> list:
        skill_names = []
        for key, value in self.skills.items():
            if "Passive Skill" not in value["type"]:
                skill_names.append(key)
        return skill_names

    def get_skills_type(self) -> list:
        skill_type = []
        for key, value in self.skills.items():
            if "Normal Attack" in value["type"]:
                skill_type.append("Normal Attack")
            elif "Elemental Skill" in value["type"]:
                skill_type.append("Elemental Skill")
            elif "Elemental Burst" in value["type"]:
                skill_type.append("Elemental Burst")
        return skill_type

    def get_passive_skill(self):
        passive_skill = []
        for key, value in self.skills.items():
            if "Passive Skill" in value["type"]:
                passive_skill.append(key)
        return passive_skill

    def get_skills_cost(self, skill_name):
        return self.skills[skill_name]["cost"]

    def get_skill_detail(self, skill_name):
        return self.skills[skill_name]

    def get_energy(self):
        return self._energy

    def change_energy(self, value):
        if self._energy + value < 0:
            return False
        else:
            self._energy += value
            return True

    def set_energy(self, value):
        self._energy = value

    def get_saturation(self):
        return self._saturation

    def change_saturation(self, value):
        self._saturation += eval(value)

    def cleat_saturation(self):
        self._saturation = 0


character_info = read_json("character.json")
