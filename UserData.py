class UserData:
    def __init__(self, user_id, points, level, xp):
        self.user_id = user_id
        self.points = points
        self.level = level
        self.xp = xp

    def get_user_id(self):
        return self.user_id

    def get_level(self):
        return self.level

    def get_points(self):
        return self.points

    def get_xp(self):
        return self.xp

    def get_rank(self):
        if self.level == 1:
            return "F5"
        if self.level == 2:
            return "F4"
        if self.level == 3:
            return "F3"
        if self.level == 4:
            return "F2"
        if self.level == 5:
            return "F1"
        if self.level == 6:
            return "E5"
        if self.level == 7:
            return "E4"
        if self.level == 8:
            return "E3"
        if self.level == 9:
            return "E2"
        if self.level == 10:
            return "E1"
        if self.level == 11:
            return "D5"
        if self.level == 12:
            return "D4"
        if self.level == 13:
            return "D3"
        if self.level == 14:
            return "D2"
        if self.level == 15:
            return "D1"
        if self.level == 16:
            return "C3"
        if self.level == 17:
            return "C2"
        if self.level == 18:
            return "C1"
        if self.level == 19:
            return "B3"
        if self.level == 20:
            return "B2"
        if self.level == 21:
            return "B1"
        if self.level == 22:
            return "A3"
        if self.level == 23:
            return "A2"
        if self.level == 24:
            return "A1"
        if self.level == 25:
            return "S2"
        if self.level == 26:
            return "S1"
        if self.level == 27:
            return "SS"

    def set_points(self, points):
        self.points = points

    def set_level(self, level):
        self.level = level

    def set_xp(self, xp):
        self.xp = xp

    def update_points(self, points):
        self.points += points

    def update_level(self, level):
        self.level += level

    def update_xp(self, xp):
        self.xp += xp
