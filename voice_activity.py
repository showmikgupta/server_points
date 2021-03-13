from datetime import datetime

class VoiceActivityNode:
	def __init__(self, guild, user, muted = False, deafened = False):
		self.guild = guild
		self.user = user
		self.muted = muted
		self.deafened = deafened
		self.points_accumulated = 0
	
	def mute(self):
		self.muted = True
	
	def unmute(self):
		self.muted = False
	
	def deafen(self):
		self.deafened = True
		self.mute = True
	
	def undeafen(self):
		self.deafened = False
		self.mute = False
	
	def add_points(self):
		if not (self.muted or self.deafened):
			self.points_accumulated += 15

	def get_points(self):
		return self.points_accumulated
	
