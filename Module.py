import sys

import pygame
from pygame.locals import *

class Module(object):
    def __init__(self, name, data, rotation, tile_size):
        self.count = 0
        self.name = name
        self.rotation = rotation
        self.self_attraction = data.get("self_attraction", 1)

        self.neighbors = data["neighbors"]
        self.links = []
        for i in range(4):
            self.links.append(set())

        self.load_sprite(data["sprite_name"], tile_size)

    def load_sprite(self, sprite_path, tile_size):
        self.sprite = pygame.image.load(
            f"""./assets/{sprite_path}""")
        # Transform it to a pygame friendly format (quicker drawing)
        self.sprite.convert()
        self.sprite = pygame.transform.scale(self.sprite,
                                            (tile_size, tile_size))
        # ALL PYGAME ROTATIONS ARE COUNTERCLOCKWISE
        if self.rotation != 0:
            self.sprite = pygame.transform.rotate(self.sprite, self.rotation)
        top = self.neighbors[0]
        right = self.neighbors[1]
        bottom = self.neighbors[2]
        left = self.neighbors[3]
        if self.rotation == 90:
            self.neighbors = [right, bottom, left, top]
        elif self.rotation == 180:
            self.neighbors = [bottom, left, top, right]
        elif self.rotation == 270:
            self.neighbors = [left, top, right, bottom]

    def create_link(self, nodeB, direction):
        self.links[direction].add(nodeB)

    def __repr__(self):
        return f"{self.name:<20} {self.count}"


class Position(object):
    def __init__(self, y, x):
        self.x = x
        self.y = y

    def __repr__(self):
        return f"x:{self.x} y:{self.y}"
