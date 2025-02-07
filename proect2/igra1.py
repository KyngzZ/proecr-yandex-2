import pygame
import sqlite3
import random
import os
import math

pygame.init()
# --- Загрузка звуков и музыки ---
pygame.mixer.init()

# Музыка
pygame.mixer.music.load("assets/Мызыка/начало.mp3")  # Музыка для меню
game_music = "assets/Мызыка/игра.mp3"  # Музыка во время игры
end_music = "assets/Мызыка/конец.mp3"  # Музыка в концовке

# Звуки
gunshot_sound = pygame.mixer.Sound("assets/Мызыка/одиночка.mp3")  # Звук выстрела
firework_sound = pygame.mixer.Sound("assets/Мызыка/живой фирверк.mp3")  # Звук фейерверка

WIDTH, HEIGHT = pygame.display.Info().current_w, pygame.display.Info().current_h
screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.FULLSCREEN)
pygame.display.set_caption("Кооперативная арена")
clock = pygame.time.Clock()

font = pygame.font.Font(None, 74)
button_font = pygame.font.Font(None, 36)

# Глобальная переменная для телепортации (переход после первого босса)
teleported = False
boss_spawned = False  # Флаг для первого босса, чтобы он спавнился только один раз

# --- Классы игры ---

class Block(pygame.sprite.Sprite):
    def __init__(self, x, y, width, height):
        super().__init__()

        try:
            image = pygame.image.load("assets/блоки/block.jpg").convert_alpha()
            self.image = pygame.transform.scale(image, (width, height))

        except Exception as e:
            print("Ошибка загрузки текстуры блоков, используется заливка:", e)
            self.image = pygame.Surface((width, height))
            self.image.fill((128, 128, 128))
        self.rect = self.image.get_rect(topleft=(x, y))

class Portal(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()
        self.frames = []  # Храним кадры анимации
        self.current_frame = 0  # Текущий кадр
        self.animation_speed = 7  # Скорость анимации (чем меньше число, тем быстрее)
        self.frame_counter = 0  # Счетчик времени

        # Загружаем анимацию
        for i in range(1, 4):  # Предполагаем, что у нас 4 кадров

            try:
                img = pygame.image.load(f"assets/Портал/portal_{i}.png").convert_alpha()
                self.frames.append(pygame.transform.scale(img, (80, 80)))  # Размер портала

            except Exception as e:
                print(f"Ошибка загрузки кадра portal_{i}.png: {e}")

        if not self.frames:
            # Если нет изображений, создаем заглушку
            placeholder = pygame.Surface((80, 80))
            placeholder.fill((0, 255, 255))  # Цвет заглушки (голубой)
            self.frames.append(placeholder)

        self.image = self.frames[self.current_frame]
        self.rect = self.image.get_rect(center=(x, y))

    def update(self, events=None):
        """Обновляет анимацию портала"""
        self.frame_counter += 1
        if self.frame_counter >= self.animation_speed:
            self.frame_counter = 0
            self.current_frame = (self.current_frame + 1) % len(self.frames)
            self.image = self.frames[self.current_frame]


class Player(pygame.sprite.Sprite):
    def __init__(self, image_files, fallback_color, controls):
        super().__init__()
        self.images = {}
        directions = ["up", "down", "left", "right"]
        for direction in directions:
            try:
                self.images[direction] = pygame.image.load(image_files[direction]).convert_alpha()
                self.images[direction] = pygame.transform.scale(self.images[direction], (50, 50))
            except Exception as e:
                print(f"Ошибка загрузки изображения {image_files[direction]}, используется заливка:", e)
                self.images[direction] = pygame.Surface((50, 50))
                self.images[direction].fill(fallback_color)

        self.image = self.images["down"]
        self.rect = self.image.get_rect()
        self.health = 100
        self.resources = 5
        self.controls = controls
        self.kills = 0
        self.direction = "down"
        self.can_shoot = True  # Можно ли стрелять?

    def update(self, events=None):  # events теперь необязательный параметр
        keys = pygame.key.get_pressed()
        dx, dy = 0, 0

        if keys[self.controls['UP']]:
            dy = -5
            self.image = self.images["up"]
            self.direction = "up"
        if keys[self.controls['DOWN']]:
            dy = 5
            self.image = self.images["down"]
            self.direction = "down"
        if keys[self.controls['LEFT']]:
            dx = -5
            self.image = self.images["left"]
            self.direction = "left"
        if keys[self.controls['RIGHT']]:
            dx = 5
            self.image = self.images["right"]
            self.direction = "right"

        self.rect.x += dx
        if pygame.sprite.spritecollideany(self, blocks):
            self.rect.x -= dx
        self.rect.y += dy
        if pygame.sprite.spritecollideany(self, blocks):
            self.rect.y -= dy

        # Разрешить стрельбу, когда кнопка отпущена
        if events:
            for event in events:
                if event.type == pygame.KEYUP and event.key == self.controls['SHOOT']:
                    self.can_shoot = True

    def shoot(self):
        if self.is_alive() and self.can_shoot:
            projectile = Projectile(self.rect.centerx, self.rect.centery, self.direction, self)
            all_sprites.add(projectile)
            projectiles.add(projectile)
            gunshot_sound.play()
            self.can_shoot = False  # Блокируем стрельбу, пока кнопка не будет отпущена

    def draw_health(self):
        if self.health > 0:
            health_ratio = self.health / 100
            pygame.draw.rect(screen, (255, 0, 0), (self.rect.centerx - 25, self.rect.top - 10, 50, 5))
            pygame.draw.rect(screen, (0, 255, 0), (self.rect.centerx - 25, self.rect.top - 10, 50 * health_ratio, 5))

    def is_alive(self):
        return self.health > 0


class Enemy(pygame.sprite.Sprite):
    def __init__(self, image_files, fallback_color):
        super().__init__()
        self.images = {}
        directions = ["up", "down", "left", "right"]
        for direction in directions:
            try:
                self.images[direction] = pygame.image.load(image_files[direction]).convert_alpha()
                self.images[direction] = pygame.transform.scale(self.images[direction], (40, 40))
            except Exception as e:
                print(f"Ошибка загрузки {image_files[direction]}, используется заливка:", e)
                self.images[direction] = pygame.Surface((40, 40))
                self.images[direction].fill(fallback_color)

        self.image = self.images["down"]  # Начальный спрайт (вниз)
        self.rect = self.image.get_rect()
        self.rect.x = random.randint(0, WIDTH - 40)
        self.rect.y = random.randint(-100, 0)
        self.health = 5
        self.last_attack_time = pygame.time.get_ticks()
        self.direction = "down"

    def is_alive(self):
        return self.health > 0

    def update(self, events=None):
        def distance_squared(rect1, rect2):
            dx = rect1.centerx - rect2.centerx
            dy = rect1.centery - rect2.centery
            return dx ** 2 + dy ** 2

        target = min(
            (player1, player2),
            key=lambda p: distance_squared(self.rect, p.rect) if p.is_alive() else float('inf')
        )

        dx, dy = 0, 0
        if target.is_alive():
            if self.rect.x < target.rect.x:
                dx = 2
                self.direction = "right"
            elif self.rect.x > target.rect.x:
                dx = -2
                self.direction = "left"
            if self.rect.y < target.rect.y:
                dy = 2
                self.direction = "down"
            elif self.rect.y > target.rect.y:
                dy = -2
                self.direction = "up"

        self.image = self.images[self.direction]  # Обновляем спрайт врага

        self.rect.x += dx
        self.rect.y += dy

        if pygame.sprite.spritecollideany(self, blocks):
            self.rect.x -= dx
            self.rect.y -= dy

        if pygame.sprite.spritecollideany(self, blocks):
            self.rect.x -= 2
            self.rect.y -= 2

        if pygame.sprite.collide_rect(self, target):
            current_time = pygame.time.get_ticks()
            if current_time - self.last_attack_time > 1000:
                target.health -= 10
                self.last_attack_time = current_time

class Boss(Enemy):
    def __init__(self):
        super().__init__({
            "up": "assets/Враги/босс2up.png",
            "down": "assets/Враги/босс1dw.png",
            "left": "assets/Враги/боссlf.png",
            "right": "assets/Враги/босс1rt.png"
        }, (255, 128, 0))  # fallback_color — если нет спрайтов

        self.image = self.images["down"]
        self.rect = self.image.get_rect(center=(WIDTH // 2, 100))
        self.health = 300
        self.last_attack_time = pygame.time.get_ticks()
        self.direction = "down"

    def update(self, events=None):
        super().update()
        self.image = self.images[self.direction]

    def draw_health(self):
        health_ratio = self.health / 300
        pygame.draw.rect(screen, (255, 0, 0), (WIDTH // 2 - 150, 20, 300, 20))
        pygame.draw.rect(screen, (0, 255, 0), (WIDTH // 2 - 150, 20, 300 * health_ratio, 20))

    def attack(self):
        current_time = pygame.time.get_ticks()
        if current_time - self.last_attack_time > 2000:
            target = random.choice([player1, player2])
            if target.is_alive():
                target.health -= 20
            self.last_attack_time = current_time


class Boss2Bullet(pygame.sprite.Sprite):
    def __init__(self, x, y, dx, dy, damage=5):
        super().__init__()
        self.image = pygame.Surface((8, 8))
        self.image.fill((255, 255, 0))
        self.rect = self.image.get_rect(center=(x, y))
        self.dx = dx
        self.dy = dy
        self.damage = damage

    def update(self, events=None):
        self.rect.x += self.dx
        self.rect.y += self.dy

        if pygame.sprite.spritecollideany(self, blocks):
            self.kill()

        for player in (player1, player2):
            if pygame.sprite.collide_rect(self, player):
                player.health -= self.damage
                self.kill()


class HomingBullet(pygame.sprite.Sprite):
    def __init__(self, x, y, target):
        super().__init__()
        self.image = pygame.Surface((10, 10))
        self.image.fill((255, 0, 0))
        self.rect = self.image.get_rect(center=(x, y))
        self.target = target
        self.speed = 4

    def update(self, events=None):
        if self.target.is_alive():
            dx = self.target.rect.centerx - self.rect.centerx
            dy = self.target.rect.centery - self.rect.centery
            distance = math.sqrt(dx ** 2 + dy ** 2)
            if distance > 0:
                self.rect.x += int(self.speed * dx / distance)
                self.rect.y += int(self.speed * dy / distance)

        if pygame.sprite.collide_rect(self, self.target):
            self.target.health -= 15  # Наносит урон при попадании
            self.kill()


class Boss2(pygame.sprite.Sprite):
    def __init__(self):
        super().__init__()
        self.images = {}
        directions = ["up", "down", "left", "right"]
        for direction in directions:
            try:
                self.images[direction] = pygame.image.load(f"assets/Враги/boss2_{direction}.png").convert_alpha()
                self.images[direction] = pygame.transform.scale(self.images[direction], (100, 100))
            except Exception as e:
                print(f"Ошибка загрузки boss2_{direction}.png, используется заливка:", e)
                self.images[direction] = pygame.Surface((100, 100))
                self.images[direction].fill((128, 0, 128))  # Фиолетовый цвет, если нет спрайта

        self.image = self.images["down"]
        self.rect = self.image.get_rect(center=(WIDTH // 2, 150))
        self.health = 700
        self.last_attack_time = pygame.time.get_ticks()
        self.last_shot_time = pygame.time.get_ticks()
        self.direction = "down"
        self.target_player = None
        self.stop_movement = False
        self.bullet_group = pygame.sprite.Group()  # <-- Добавлено: теперь пули не вызывают ошибку

    def is_alive(self):
        return self.health > 0

    def update(self, events=None):
        now = pygame.time.get_ticks()
        # Преследует игрока
        if not self.stop_movement:
            self.move_towards_player()

        # Постоянная стрельба каждые 1 секунду
        if now - self.last_shot_time > 1000:
            self.shoot_bullets()
            self.last_shot_time = now

        # Каждые 5 секунд делает мощную атаку
        if now - self.last_attack_time > 5000:
            self.stop_movement = True  # Остановка перед атакой
            self.shoot_big_attack()
            self.last_attack_time = now
        self.bullet_group.update()

    def move_towards_player(self):
        players = [player1, player2]
        self.target_player = min(players, key=lambda p: self.distance_squared(p)) if players else None

        if self.target_player and self.target_player.is_alive():
            if self.rect.x < self.target_player.rect.x:
                self.rect.x += 2
            elif self.rect.x > self.target_player.rect.x:
                self.rect.x -= 2
            if self.rect.y < self.target_player.rect.y:
                self.rect.y += 2
            elif self.rect.y > self.target_player.rect.y:
                self.rect.y -= 2

    def shoot_bullets(self):
        # Простая стрельба (постоянно)
        for angle in range(0, 360, 90):
            rad = math.radians(angle)
            dx = int(5 * math.cos(rad))
            dy = int(5 * math.sin(rad))
            bullet = Boss2Bullet(self.rect.centerx, self.rect.centery, dx, dy)
            self.bullet_group.add(bullet)
            all_sprites.add(bullet)

    def shoot_big_attack(self):
        # Волна из пуль
        for angle in range(0, 360, 45):
            rad = math.radians(angle)
            dx = int(5 * math.cos(rad))
            dy = int(5 * math.sin(rad))
            bullet = Boss2Bullet(self.rect.centerx, self.rect.centery, dx, dy)
            self.bullet_group.add(bullet)
            all_sprites.add(bullet)

        # Запуск самонаводящейся пули
        if self.target_player and self.target_player.is_alive():
            homing_bullet = HomingBullet(self.rect.centerx, self.rect.centery, self.target_player)
            self.bullet_group.add(homing_bullet)
            all_sprites.add(homing_bullet)

    def draw_health(self):
        health_ratio = self.health / 700
        pygame.draw.rect(screen, (255, 0, 0), (WIDTH // 2 - 150, 20, 300, 20))
        pygame.draw.rect(screen, (0, 255, 0), (WIDTH // 2 - 150, 20, 300 * health_ratio, 20))

    def distance_squared(self, player):
        dx = self.rect.centerx - player.rect.centerx
        dy = self.rect.centery - player.rect.centery
        return dx ** 2 + dy ** 2


class BlackHole(pygame.sprite.Sprite):
    # После смерти первого босса – портал для телепортации
    def __init__(self, x, y):
        super().__init__()
        self.image = pygame.Surface((100, 100), pygame.SRCALPHA)
        pygame.draw.circle(self.image, (0, 0, 0, 200), (50, 50), 50)
        self.rect = self.image.get_rect(center=(x, y))

    def update(self, events=None):
        for player in [player1, player2]:
            if player.is_alive() and pygame.sprite.collide_rect(self, player):
                teleport_players()


class Projectile(pygame.sprite.Sprite):
    def __init__(self, x, y, direction, shooter):
        super().__init__()
        self.image = pygame.Surface((10, 10))
        self.image.fill((255, 255, 0))
        self.rect = self.image.get_rect(center=(x, y))
        self.direction = direction
        self.speed = 7
        self.shooter = shooter  # Новый параметр

    def update(self, events=None):
        if self.direction == "up":
            self.rect.y -= self.speed
        elif self.direction == "down":
            self.rect.y += self.speed
        elif self.direction == "left":
            self.rect.x -= self.speed
        elif self.direction == "right":
            self.rect.x += self.speed

        # Удаление пули, если она выходит за границы экрана
        if self.rect.bottom < 0 or self.rect.top > HEIGHT or self.rect.right < 0 or self.rect.left > WIDTH:
            self.kill()

        if pygame.sprite.spritecollideany(self, blocks):
            self.kill()

# --- Функции управления локациями и волнами ---

def setup_wave(wave, location="default"):
    global all_sprites, blocks, player1, player2
    all_sprites = pygame.sprite.Group()
    blocks = pygame.sprite.Group()
    # Создаем игроков
    player1 = Player({
        "up": "assets/Солдаты/перс3.png",
        "down": "assets/Солдаты/перс4.png",
        "left": "assets/Солдаты/перс2.png",
        "right": "assets/Солдаты/перс1.png"
    }, (0, 255, 0), player1_controls)

    player2 = Player({
        "up": "assets/Солдаты/соладаь3.png",
        "down": "assets/Солдаты/соладаь4.png",
        "left": "assets/Солдаты/соладаь2.png",
        "right": "assets/Солдаты/соладаь.png"
    }, (0, 0, 255), player2_controls)

    if location == "default":
        player1.rect.center = (WIDTH // 4, HEIGHT - 100)
        player2.rect.center = (WIDTH * 3 // 4, HEIGHT - 100)
    else:
        player1.rect.center = (WIDTH // 3, HEIGHT - 150)
        player2.rect.center = (WIDTH * 2 // 3, HEIGHT - 150)
    all_sprites.add(player1, player2)
    enemies_group = pygame.sprite.Group()
    for _ in range(wave * 5):

        # Создаём врагов
        enemy = Enemy({
            "up": "assets/Враги/врагup.png",
            "down": "assets/Враги/врагdw.png",
            "left": "assets/Враги/врагlf.png",
            "right": "assets/Враги/врагrt.png"
        }, (255, 0, 0))  # fallback_color — если изображения нет
        all_sprites.add(enemy)
        enemies_group.add(enemy)
    # Генерация блоков без наложения на игроков и портал (если он есть)
    for i in range(5):
        placed = False
        attempts = 0
        while not placed and attempts < 100:
            x = random.randint(0, WIDTH - 100)
            y = random.randint(0, HEIGHT - 100) if location == "default" else random.randint(100, HEIGHT - 200)
            block = Block(x, y, 100, 50)
            collides = False
            for sprite in [player1, player2]:
                if block.rect.colliderect(sprite.rect):
                    collides = True
                    break
            if 'portal' in globals() and portal is not None:
                if block.rect.colliderect(portal.rect):
                    collides = True
            if not collides:
                placed = True
            attempts += 1
        if placed:
            blocks.add(block)
            all_sprites.add(block)
    return enemies_group

def teleport_players():
    global teleported, game_bg, current_wave, wave
    teleported = True
    print("Телепортация! Новая локация.")
    try:
        game_bg = pygame.image.load("game_background2.jpg").convert()
        game_bg = pygame.transform.scale(game_bg, (WIDTH, HEIGHT))
    except Exception as e:
        print("Новый фон не найден, используется plain background.", e)
        game_bg = None
    current_wave = wave + 1  # следующая волна
    wave = current_wave
    new_enemies = setup_wave(current_wave, location="new")
    return new_enemies

def loading_screen():
    progress = 0
    loading_duration = 3000
    start_time = pygame.time.get_ticks()
    while progress < 100:
        current_time = pygame.time.get_ticks()
        progress = min(100, ((current_time - start_time) / loading_duration) * 100)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return
        screen.fill((0, 0, 0))
        bar_width = WIDTH // 2
        bar_height = 40
        bar_x = (WIDTH - bar_width) // 2
        bar_y = (HEIGHT - bar_height) // 2
        pygame.draw.rect(screen, (255, 255, 255), (bar_x, bar_y, bar_width, bar_height), 3)
        inner_width = int(bar_width * (progress / 100))
        pygame.draw.rect(screen, (0, 255, 0), (bar_x, bar_y, inner_width, bar_height))
        loading_text = font.render("Loading...", True, (255, 255, 255))
        text_rect = loading_text.get_rect(center=(WIDTH // 2, bar_y - 50))
        screen.blit(loading_text, text_rect)
        pygame.display.flip()
        clock.tick(60)

def pause_menu():
    paused = True
    while paused:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_c:
                    paused = False
                elif event.key == pygame.K_m:
                    main_menu()
                    pygame.quit()
                    return
        overlay = pygame.Surface((WIDTH, HEIGHT))
        overlay.set_alpha(150)
        overlay.fill((0, 0, 0))
        screen.blit(overlay, (0, 0))
        pause_text = font.render("Пауза", True, (255, 255, 255))
        continue_text = button_font.render("Нажмите C, чтобы продолжить", True, (255, 255, 255))
        menu_text = button_font.render("Нажмите M, чтобы выйти в меню", True, (255, 255, 255))
        screen.blit(pause_text, pause_text.get_rect(center=(WIDTH//2, HEIGHT//2 - 100)))
        screen.blit(continue_text, continue_text.get_rect(center=(WIDTH//2, HEIGHT//2)))
        screen.blit(menu_text, menu_text.get_rect(center=(WIDTH//2, HEIGHT//2 + 50)))
        pygame.display.flip()
        clock.tick(60)

def death_screen():
    pygame.mixer.music.stop()  # Останавливаем текущую музыку
    pygame.mixer.music.load("assets/Мызыка/начало.mp3")  # Загружаем музыку меню
    pygame.mixer.music.play(-1)  # Запускаем музыку меню в цикле

    try:
        print("Игрок умер. Сохраняем счёт...")
        save_score(wave, player1.kills, player2.kills)
    except Exception as e:
        print("Ошибка при сохранении счёта в death_screen:", e)
    waiting = True
    while waiting:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r:
                    game()  # Перезапуск игры (игровая музыка загрузится в `game()`)
                    return
                elif event.key == pygame.K_m:
                    main_menu()  # Возвращение в меню
                    return

        screen.fill((0, 0, 0))
        death_text = font.render("ПОМЕР", True, (255, 0, 0))
        death_rect = death_text.get_rect(center=(WIDTH//2, HEIGHT//2 - 100))
        screen.blit(death_text, death_rect)

        option_text = button_font.render("Нажмите R для перезапуска или M для меню", True, (255, 255, 255))
        option_rect = option_text.get_rect(center=(WIDTH//2, HEIGHT//2))
        screen.blit(option_text, option_rect)

        pygame.display.flip()
        clock.tick(60)

def end_sequence():
    pygame.mixer.music.stop()
    pygame.mixer.music.load(end_music)
    pygame.mixer.music.play(-1)
    global player1, player2, wave
    firework_duration = 3000
    start_time = pygame.time.get_ticks()
    while pygame.time.get_ticks() - start_time < firework_duration:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return
        screen.fill((0, 0, 0))
        for _ in range(10):
            x = random.randint(0, WIDTH)
            y = random.randint(0, HEIGHT)
            radius = random.randint(10, 50)
            color = (random.randint(200, 255), random.randint(200, 255), random.randint(200, 255))
            pygame.draw.circle(screen, color, (x, y), radius)
        pygame.display.flip()
        clock.tick(60)
    door_rect = pygame.Rect(WIDTH//2 - 100, HEIGHT//2 - 150, 200, 300)
    door_entered = False
    while not door_entered:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN:
                    door_entered = True
        screen.fill((0, 0, 0))
        pygame.draw.rect(screen, (139, 69, 19), door_rect)
        text = button_font.render("Нажмите Enter, чтобы войти", True, (255, 255, 255))
        text_rect = text.get_rect(center=(WIDTH//2, HEIGHT//2 + 200))
        screen.blit(text, text_rect)
        pygame.display.flip()
        clock.tick(60)
    scroll_text_lines = [
        "Создатель: kyng_zZ",
        "and Бирюков Кирилл Николаевич",
        "and Танкист",
        "and хакер",
        "and взлом пентогана onnnn",
        "Спасибо за то что прошли мою игру!",
        "Вы уничтожили солевых на моложёжке и спасли мир.",
        "А ну и Артур самый лучший учитель",
        "Нажмите любую клавишу, чтобы продолжить..."
    ]
    y = -200
    scroll_speed = 1
    done_scrolling = False
    while not done_scrolling:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return
            if event.type == pygame.KEYDOWN:
                done_scrolling = True
        screen.fill((0, 0, 0))
        for i, line in enumerate(scroll_text_lines):
            text = font.render(line, True, (255, 255, 255))
            text_rect = text.get_rect(center=(WIDTH//2, y + i * 80))
            screen.blit(text, text_rect)
        pygame.display.flip()
        clock.tick(60)
        y += scroll_speed
        if y + (len(scroll_text_lines)-1)*80 > HEIGHT - 50:
            pygame.time.delay(2000)
            done_scrolling = True

    pygame.mixer.music.stop()
    pygame.mixer.music.load("assets/Мызыка/начало.mp3")
    pygame.mixer.music.play(-1)
    waiting = True

    while waiting:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return
            if event.type == pygame.KEYDOWN:
                waiting = False
        screen.fill((0, 0, 0))
        score_text = font.render(f"Волны: {wave}  Убийств P1: {player1.kills}  Убийств P2: {player2.kills}", True, (255, 255, 255))
        score_rect = score_text.get_rect(center=(WIDTH//2, HEIGHT//2))
        screen.blit(score_text, score_rect)
        button_text = button_font.render("Нажмите любую клавишу, чтобы вернуться в меню", True, (255, 255, 255))
        button_rect = button_text.get_rect(center=(WIDTH//2, HEIGHT//2 + 100))
        screen.blit(button_text, button_rect)
        pygame.display.flip()
        clock.tick(60)
    main_menu()

# --- Основная функция игры ---

def game():
    pygame.mixer.music.load(game_music)
    pygame.mixer.music.play(-1)
    global all_sprites, projectiles, blocks, player1, player2, portal, wave, enemies, boss, game_bg, current_wave, teleported, boss_spawned
    wave = 1
    current_wave = wave
    portal = None
    boss = None
    teleported = False
    boss_spawned = False

    try:
        game_bg = pygame.image.load("game_background.jpg").convert()
        game_bg = pygame.transform.scale(game_bg, (WIDTH, HEIGHT))
    except Exception as e:
        print("Фоновое изображение игры не найдено, используется plain background.", e)
        game_bg = None

    global player1_controls, player2_controls
    player1_controls = {'UP': pygame.K_w, 'DOWN': pygame.K_s, 'LEFT': pygame.K_a, 'RIGHT': pygame.K_d, 'SHOOT': pygame.K_SPACE}
    player2_controls = {'UP': pygame.K_UP, 'DOWN': pygame.K_DOWN, 'LEFT': pygame.K_LEFT, 'RIGHT': pygame.K_RIGHT, 'SHOOT': pygame.K_RETURN}

    enemies = setup_wave(wave)
    projectiles = pygame.sprite.Group()
    running = True
    game_over = False

    while running:
        events = pygame.event.get()  # Получаем все события
        for event in events:
            if event.type == pygame.QUIT:
                pygame.quit()
                return
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pause_menu()
                if player1.is_alive() and event.key == player1.controls['SHOOT']:
                    player1.shoot()
                if player2.is_alive() and event.key == player2.controls['SHOOT']:
                    player2.shoot()

        if not game_over:
            all_sprites.update(events)
            keys = pygame.key.get_pressed()
            if player1.is_alive() and keys[player1.controls['SHOOT']]:
                player1.shoot()
            if player2.is_alive() and keys[player2.controls['SHOOT']]:
                player2.shoot()

            for projectile in projectiles:
                hit_enemies = pygame.sprite.spritecollide(projectile, enemies, False)
                for enemy in hit_enemies:
                    enemy.health -= 10
                    projectile.kill()
                    if enemy.health <= 0:
                        enemy.kill()
                        projectile.shooter.kills += 1

            if not player1.is_alive():
                player1.kill()
            if not player2.is_alive():
                player2.kill()
            if not player1.is_alive() and not player2.is_alive():
                game_over = True

            # Логика волн и появления объектов:
            if len(enemies) == 0:
                if wave < 5:
                    if portal is None:
                        portal = Portal(WIDTH//2, HEIGHT//2)
                        all_sprites.add(portal)
                elif wave == 5:
                    # Спавним первого босса только один раз на волне 5
                    if not boss_spawned:
                        if boss is None:
                            boss = Boss()
                            all_sprites.add(boss)
                            enemies.add(boss)
                            boss_spawned = True
                    # Если первый босс погиб, оставляем только портал
                    if boss is not None and not boss.is_alive():
                        boss = None
                        if portal is None:
                            portal = Portal(WIDTH//2, HEIGHT//2)
                            all_sprites.add(portal)
                elif wave >= 6 and wave < 10:
                    if portal is None:
                        portal = Portal(WIDTH//2, HEIGHT//2)
                        all_sprites.add(portal)
                elif wave >= 10:
                    if boss is None:
                        boss = Boss2()
                        all_sprites.add(boss)
                        enemies.add(boss)

            # Переход через портал
            if portal and (pygame.sprite.collide_rect(player1, portal) or pygame.sprite.collide_rect(player2, portal)):
                portal.kill()
                portal = None
                wave += 1
                current_wave = wave
                enemies = setup_wave(wave, location="default" if not teleported else "new")

            # Если второй босс (Boss2) погиб, запускаем финальную последовательность
            if boss and isinstance(boss, Boss2) and not boss.is_alive():
                end_sequence()
                return

            if game_bg:
                screen.blit(game_bg, (0, 0))
            else:
                screen.fill((0, 0, 0))
            all_sprites.draw(screen)
            if player1.is_alive():
                player1.draw_health()
            if player2.is_alive():
                player2.draw_health()
            if boss and hasattr(boss, "draw_health"):
                boss.draw_health()

            pygame.display.flip()
            clock.tick(60)
        else:
            death_screen()
            return

    print("Игра окончена, сохраняем счёт...")
    save_score(wave, player1.kills, player2.kills)
    main_menu()
# ============ Функции работы с базой данных

def save_score(wave, kills1, kills2):
    try:
        conn = sqlite3.connect("highscores.db")
        c = conn.cursor()
        # Создаем таблицу, если её ещё нет (в старой схеме)
        c.execute("""
            CREATE TABLE IF NOT EXISTS scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wave INTEGER,
                kills1 INTEGER,
                kills2 INTEGER
            )
        """)
        conn.commit()
        # Проверяем наличие столбца score
        c.execute("PRAGMA table_info(scores)")
        columns = [info[1] for info in c.fetchall()]
        if "score" not in columns:
            c.execute("ALTER TABLE scores ADD COLUMN score INTEGER")
            conn.commit()

        total_score = wave * 100 + (kills1 + kills2) * 10

        c.execute("INSERT INTO scores (wave, kills1, kills2, score) VALUES (?, ?, ?, ?)",
                  (wave, kills1, kills2, total_score))
        conn.commit()
        conn.close()
        print("Счёт успешно сохранён:", wave, kills1, kills2, total_score)
    except Exception as e:
        print("Ошибка сохранения счёта:", e)

def show_best_score():
    if not pygame.get_init():
        return
    try:
        conn = sqlite3.connect("highscores.db")
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wave INTEGER,
                kills1 INTEGER,
                kills2 INTEGER,
                score INTEGER
            )
        """)
        conn.commit()
        c.execute("SELECT wave, kills1, kills2, score FROM scores ORDER BY score DESC LIMIT 1")
        result = c.fetchone()
        conn.close()
    except Exception as e:
        print("Ошибка загрузки счёта:", e)
        result = None

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_RETURN):
                    running = False
        screen.fill((0, 0, 0))
        title = font.render("Лучший счёт", True, (255, 255, 255))
        title_rect = title.get_rect(center=(WIDTH // 2, HEIGHT // 4))
        screen.blit(title, title_rect)
        if result:
            wave_score, kills1, kills2, total_score = result
            score_text = button_font.render(
                f"Волны: {wave_score}, P1: {kills1}, P2: {kills2} | Итоговый счёт: {total_score}",
                True, (255, 255, 255)
            )
        else:
            score_text = button_font.render("Нет записей", True, (255, 255, 255))
        score_rect = score_text.get_rect(center=(WIDTH // 2, HEIGHT // 2))
        screen.blit(score_text, score_rect)
        instruction_text = button_font.render("Нажмите Enter или Esc, чтобы вернуться", True, (255, 255, 255))
        instruction_rect = instruction_text.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 50))
        screen.blit(instruction_text, instruction_rect)
        pygame.display.flip()
        clock.tick(60)

def battlefield_description():
    running = True
    description_lines = [
        "Битва проходит на заброшенной территории-молодёжка,",
        "где остатки старых разрушенных домов",
        "создают укрытия для бойцов.",
        "Осторожно – за каждым углом может скрываться опасность! в виде солевых",
        "",
        "Управление 1 перс:стрелочки стреляет на ентер",
        "Управление 2 перс:wasd стреляет на пробел"
    ]
    start_button_rect = pygame.Rect(WIDTH//2 - 150, HEIGHT - 150, 300, 50)
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return
            if event.type == pygame.MOUSEBUTTONDOWN:
                mouse_pos = event.pos
                if start_button_rect.collidepoint(mouse_pos):
                    running = False
        screen.fill((20, 20, 20))
        title = font.render("Поле битвы", True, (255, 255, 255))
        title_rect = title.get_rect(center=(WIDTH//2, HEIGHT//4))
        screen.blit(title, title_rect)

        for i, line in enumerate(description_lines):
            line_surf = button_font.render(line, True, (200, 200, 200))
            line_rect = line_surf.get_rect(center=(WIDTH//2, HEIGHT//2 - 50 + i * 40))
            screen.blit(line_surf, line_rect)

        pygame.draw.rect(screen, (255, 255, 255), start_button_rect)
        button_text = button_font.render("Начать битву", True, (0, 0, 0))
        button_text_rect = button_text.get_rect(center=start_button_rect.center)
        screen.blit(button_text, button_text_rect)
        pygame.display.flip()
        clock.tick(60)

def main_menu():
    pygame.mixer.music.load("assets/Мызыка/начало.mp3")  # Загружаем музыку меню
    pygame.mixer.music.play(-1)  # Запускаем музыку меню в цикле

    try:
        bg = pygame.image.load("assets/блоки/fon.jpg").convert()
        bg = pygame.transform.scale(bg, (WIDTH, HEIGHT))
    except Exception as e:
        print("Background image not found, using plain background.", e)
        bg = None

    running = True
    while running:
        play_button_rect = pygame.Rect(WIDTH//2 - 100, HEIGHT//2 - 60, 200, 50)
        score_button_rect = pygame.Rect(WIDTH//2 - 100, HEIGHT//2, 200, 50)
        exit_button_rect = pygame.Rect(WIDTH//2 - 100, HEIGHT//2 + 60, 200, 50)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return
            if event.type == pygame.MOUSEBUTTONDOWN:
                mouse_pos = event.pos
                if play_button_rect.collidepoint(mouse_pos):
                    battlefield_description()
                    loading_screen()
                    game()
                elif score_button_rect.collidepoint(mouse_pos):
                    show_best_score()
                elif exit_button_rect.collidepoint(mouse_pos):
                    pygame.quit()
                    return

        if bg:
            screen.blit(bg, (0, 0))
        else:
            screen.fill((0, 0, 0))

        title_text = font.render("Кооперативная арена", True, (000, 000, 000))
        title_rect = title_text.get_rect(center=(WIDTH//2, HEIGHT//4))
        screen.blit(title_text, title_rect)

        pygame.draw.rect(screen, (255, 255, 255), play_button_rect)
        pygame.draw.rect(screen, (255, 255, 255), score_button_rect)
        pygame.draw.rect(screen, (255, 255, 255), exit_button_rect)

        play_text = button_font.render("Играть", True, (0, 0, 0))
        score_text = button_font.render("Лучший счёт", True, (0, 0, 0))
        exit_text = button_font.render("Выйти", True, (0, 0, 0))

        screen.blit(play_text, play_text.get_rect(center=play_button_rect.center))
        screen.blit(score_text, score_text.get_rect(center=score_button_rect.center))
        screen.blit(exit_text, exit_text.get_rect(center=exit_button_rect.center))

        pygame.display.flip()
        clock.tick(60)

if __name__ == "__main__":
    main_menu()