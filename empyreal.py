#!/usr/bin/env python2.5

from __future__ import with_statement

import curses
import curses.textpad
import curses.wrapper
import linecache
import pickle
import random
import sys

from lib import chance, rand_diff, rand_range, rand_success, read_file_lines

gamename = 'Empyreal'

COLOR_HIGHLIGHT = 9

class State:
    pass

# Saved Game State
mapw = 0
maph = 0
py = 0
px = 0
map = []
factions = {}
cities = []
units = []
turn = 0
curfac = 0
msgs = []

# Non-Saved State
type2terr = {}
unittypes = {}
mode = None
scr = None
paintbrush_terrain = 0
paintbrush_faction = 0
paintbrush_unittype = 0

class Terrain:
    def __init__(self, name, char, color,impassable=False):
        self.name = name
        self.char = char
        self.color = color
        self.impassable = impassable

type2terr = {}
type2terr[0] = Terrain('plains',   '.',6)
type2terr[1] = Terrain('mountains','^',8,True)
type2terr[2] = Terrain('water',    '~',7,True)

def terrname2id(name):
    for terrid in type2terr:
        terrain = type2terr[terrid]
        if terrain.name == name:
            return terrid
    return None

class Cell:
    def __init__(self, terr=0):
        self.terr = terr

class Faction:
    def __init__(self, name, color):
        self.name = name
        self.color = color

class UnitType:
    def __init__(self, name, char, buildcost, softatk, softdef, hardatk, harddef, hpmax, move):
        self.name = name
        self.char = char
        self.buildcost = buildcost
        self.softatk = softatk
        self.softdef = softdef
        self.hardatk = hardatk
        self.harddef = harddef
        self.hpmax = hpmax
        self.move = move
        self.buildchar = self.char.lower()

unittypes = {
    0 : UnitType('infantry',  'I',10, 3, 2, 2, 3, 2, 1),
    1 : UnitType('armor',     'A',30, 5, 9, 6, 6, 3, 2),
    2 : UnitType('partisans', 'P', 2, 1, 1, 1, 1, 1, 1)}

def type_for_name(name):
    for ut in unittypes:
        unittype = unittypes[ut]
        if unittype.name == name:
            return ut
    return None

class Unit:
    def __init__(self, owner, type, x=0, y=0):
        self.owner = owner
        self.type = type
        self.x = x
        self.y = y 
        self.moveleft = unittypes[type].move
        self.hp = unittypes[type].hpmax

def units_at(x, y):
    return [u for u in units if u.x == x and u.y == y]

class City:
    def __init__(self, name, owner, buildrate, x, y):
        self.name = name
        self.owner = owner
        self.x = x
        self.y = y
        self.building = False
        self.buildtype = 0
        self.buildprogress = 0
        self.buildrate = buildrate

def city_with_name(name):
    for c in cities:
        if c.name == name:
            return c
    return None

def get_city_at(x, y):
    for c in cities:
        if c.x == x and c.y == y:
            return c
    return None

def msgs_display_limit():
    return scr.getmaxyx()[0] - (maph + 1)

def msg(txt):
    global msgs
    if len(msgs) >= msgs_display_limit():
        msgs = msgs[1:]
    msgs.append(txt)

def centerp(row, txt):
    col = (scr.getmaxyx()[1] - len(txt)) / 2
    scr.addstr(row,col,txt)

def addstr(row, col, txt, attr=None):
    if attr is not None:
        scr.addstr(row,col,txt,attr)
    else:
        scr.addstr(row,col,txt)

def hitanykey():
    scr.getch()

def is_valid_xy(x, y):
    return x >= 0 and y >= 0 and x < mapw and y < maph

def save():
    fname = 'saves/last'
    msg('saving game to file %s' % fname)
    state = State()
    state.map = map
    state.factions = factions
    state.cities = cities
    state.units = units
    state.px = px
    state.py = py
    state.turn = turn
    state.curfac = curfac
    state.msgs = msgs
    state.mapw = mapw
    state.maph = maph
    with file(fname,'w') as f:
        pickle.dump(state,f)

def load(fname = 'saves/last'):
    global map, cities, units, factions, px, py, turn, curfac, msgs, mapw, maph

    with file(fname,'r') as f:
        state = pickle.load(f)
        map = state.map
        factions = state.factions
        cities = state.cities
        units = state.units
        px = state.px
        py = state.py
        turn = state.turn
        curfac = state.curfac
        msgs = state.msgs
        mapw = state.mapw
        maph = state.maph
        msg('game loaded from file %s' % fname)

def draw_panel_borders():
    # border between map and messages
    r = maph
    for c in range(mapw):
        addstr(r,c,'#')

    # border between map and right sidebar
    c = mapw
    for r in range(maph):
        addstr(r,c,'#')

    # corner piece to join the two lines above
    addstr(maph,mapw,'#')

def draw_city_at(city, row, col):
    attr = curses.color_pair(factions[city.owner].color)
    scr.addstr(row, col, '#', attr)

def draw_cities_on_map():
    for c in cities:
        draw_city_at(c,c.y,c.x)

def draw_unit_at(unit, row, col):
    attr = curses.color_pair(factions[unit.owner].color)
    scr.addstr(row, col, unittypes[unit.type].char, attr)

def draw_units_on_map():
    for u in units:
        draw_unit_at(u, u.y, u.x)

def draw_terrain_at(terrid, row, col):
    scr.addstr(row, col,
        type2terr[terrid].char,
        curses.color_pair(type2terr[terrid].color))

def draw_terrain_on_map():
    for x in range(mapw):
        for y in range(maph):
            draw_terrain_at(map[x][y].terr,y,x)

def draw_map():
    draw_terrain_on_map()
    draw_units_on_map()
    draw_cities_on_map()

def draw_cursor():
    addstr(py,px,'@')

def draw_messages():
    r = maph + 1
    c = 0
    ms = msgs[:msgs_display_limit()]
    for ln in ms:
        addstr(r,c,ln)
        r += 1

class EconSnapshot:
    def __init__(self, facid):
        self.facid = facid
        us = [u for u in units if u.owner == facid]
        self.unit_qty = len(us)
        self.support_need = 0
        for u in us:
            utype = unittypes[u.type]
            self.support_need += utype.buildcost
        cs = [c for c in cities if c.owner == facid]
        self.city_qty = len(cs)
        self.total_buildrate = 0
        for c in cs:
            self.total_buildrate += c.buildrate
        self.penalty_rate = 1.0
        if self.support_need > 0 and self.support_need > self.total_buildrate:
            self.penalty_rate = float(self.total_buildrate) / float(self.support_need)

    def actual_buildrate(self, city):
        assert city.owner == self.facid
        actual_rate = int(city.buildrate * self.penalty_rate)
        if city.buildrate > 0 and actual_rate < 1:
            actual_rate = 1
        return actual_rate

def put_cursor_at_active_unit():
    scr.move(py,px)

def force_valid_coords(x, y):
    y = max(0, y)
    x = max(0, x)
    y = min(y, maph-1)
    x = min(x, mapw-1)
    return x,y

def desc_unit(u):
    return '%s %s' % (factions[u.owner].name, unittypes[u.type].name)

def endturn():
    global curfac, turn

    msg("end of %s's turn %s" % (factions[curfac].name, turn))
    curfac = curfac + 1
    if curfac >= len(factions):
        curfac = 1
        turn += 1
    msg("start of %s's turn %s" % (factions[curfac].name, turn))

    # Repair Units
    for c in cities:
        if c.owner != curfac:
            continue
        units2repair = [u for u in units if u.x == c.x and u.y == c.y and u.owner == c.owner and u.hp < unittypes[u.type].hpmax]
        for u in units2repair:
            u.hp += 1
            how = (u.hp == unittypes[u.type].hpmax) and 'fully' or 'partially'
            msg('%s repairs %s in %s' % (desc_unit(u), how, c.name))

    # Refuel Units
    for u in units:
        if u.owner == curfac:
            utype = unittypes[u.type]
            maxmove = utype.move
            if u.hp < utype.hpmax and maxmove >= 2:
                maxmove -= 1
            u.moveleft = maxmove

    # Build New Units
    econ = EconSnapshot(curfac)
    for c in cities:
        if c.owner == curfac:
            c.buildprogress += econ.actual_buildrate(c)
            utid = c.buildtype
            utype = unittypes[utid]
            if c.buildprogress >= utype.buildcost:
                c.buildprogress -= utype.buildcost
                u = Unit(curfac, utid, c.x, c.y)
                units.append(u)
                msg('city %s built %s' % (c.name, desc_unit(u)))

def is_enemy_unit_there(factionid, x, y):
    for u in units:
        if u.x == x and u.y == y and u.owner != factionid:
            return True
    return False

def get_enemy_unit_there_to_attack(factionid, x, y):
    for u in units:
        if u.x == x and u.y == y and u.owner != factionid:
            return u
    return None

def destroy_unit(unit):
    units.remove(unit)

class Mode:
    name = ''

    def __init__(self):
        self.disabled_keys = {}

    def handle_getch(self, ch):
        pass

    def refresh_display(self):
        scr.erase()
        draw_panel_borders()
        draw_map()
        draw_cursor()
        draw_messages()
        self.draw_sidebar()
        put_cursor_at_active_unit()
        scr.refresh()

    def post_handle_getch(self):
        victory_check()

    def draw_sidebar(self, highlighted_units=[]):
        c = mapw + 2
        attr = curses.color_pair(factions[curfac].color)
        addstr(0, c, "%s" % factions[curfac].name, attr)
        addstr(0, c+10, 'Turn %s' % turn)
        addstr(2, c, mode.name)

        econ = EconSnapshot(curfac)
        penalty = ''
        if econ.penalty_rate < 1.0:
            penalty = ' at %.5s%%' % (econ.penalty_rate * 100.0)
        addstr(4, c, 'units: %s (- %s)' % (econ.unit_qty, econ.support_need))
        addstr(5, c, 'cities: %s (+ %s)%s' % (econ.city_qty, econ.total_buildrate, penalty))

        addstr(7, c, "%s,%s" % (px,py))
        draw_terrain_at(map[px][py].terr,8,c)
        addstr(8, c+2, "%s" % type2terr[ map[px][py].terr ].name)

        # show cities at cursor
        cr = 10
        for city in cities:
            if city.x == px and city.y == py:
                cityecon = EconSnapshot(city.owner)
                draw_city_at(city, cr, c)
                buildtxt = ''
                if city.building:
                    utype = unittypes[city.buildtype]
                    buildtxt = ' [%s %s/%s]' % (utype.char, city.buildprogress, utype.buildcost)

                actualtxt = ''
                if city.owner == curfac:
                    actual = cityecon.actual_buildrate(city)
                    if actual < city.buildrate:
                        actualtxt = '; %s' % actual
                lns = ['%s' % city.name,
                       '(%s%s)%s' % (city.buildrate, actualtxt, buildtxt)]
                for ln in lns:
                    addstr(cr,c+2,ln)
                    cr += 1

        # list units at cursor
        ur = cr + 1
        unitshere = units_at(px,py)
        if len(unitshere) >= 2:
            addstr(ur, c, 'total units: %s' % len(unitshere))
            ur += 2
        for u in unitshere:
            draw_unit_at(u, ur, c)
            attr = None
            utype = unittypes[u.type]
            if u in highlighted_units:
                attr = curses.color_pair(COLOR_HIGHLIGHT)
            addstr(ur, c+2, "%s (%s/%s) [%s/%s]" % (utype.name, u.moveleft, utype.move, u.hp, utype.hpmax), attr)
            ur += 1
            if ur >= scr.getmaxyx()[0]:
                break

class BrowseMapMode(Mode):
    name = 'Browse Map'
    unit_selected_mode = None#UnitSelectedMode #TODO hack, see end of U.S.M.

    def get_selectable_factions(self):
        return [curfac,]

    def handle_getch(self, ch):
        global mode
        if ch in self.disabled_keys:
            return
        if ch == 'Q':
            return False
        if ch == 'i':
            self.move(0,-1)
        if ch == 'u':
            self.move(-1,-1)
        if ch == 'o':
            self.move(1,-1)
        if ch == 'm':
            self.move(0,1)
        if ch == 'n':
            self.move(-1,1)
        if ch == ',':
            self.move(1,1)
        if ch == 'j':
            self.move(-1,0)
        if ch == 'k':
            self.move(1,0)
        if ch == 'T':
            endturn()
        if ch == ' ':
            self.select_unit_at_cursor()
        if ch == 'b':
            self.switch_to_SpecifyCityBuildTypeMode()
        if ch == 'S':
            save()
        if ch == 'L':
            load()
        if ch == 'd':
            mode = EditorMode()

    def switch_to_SpecifyCityBuildTypeMode(self):
        global mode
        city = get_city_at(px,py)
        if city:
            if city.owner == curfac:
                mode = SpecifyCityBuildTypeMode(city)
            else:
                msg('you do not control that city')
        else:
            msg('no city there')

    def move(self, xrel, yrel):
        global py, px
        px += xrel
        py += yrel
        px,py = force_valid_coords(px,py)
        #self.refresh_display()

    def select_unit_at_cursor(self):
        global mode
        selected = False
        for u in units:
            if u.owner not in self.get_selectable_factions():
                continue
            if u.x == px and u.y == py:
                selected = True
                #mode = UnitSelectedMode(u)
                mode = self.unit_selected_mode(u,self.get_selectable_factions())
                #mode.refresh_display()
                break
        if not selected:
            msg('no unit of yours there to select')

class EditorMode(BrowseMapMode):
    name = 'Editor Mode'
    unit_selected_mode = None#EditorUnitSelectedMode #TODO hack

    def handle_getch(self, ch):
        global mode
        retval = BrowseMapMode.handle_getch(self,ch)
        if retval is not None and not retval:
            return False
        if ch == 'D':
            self.delete_all_at_cursor()
        if ch == 'r':
            self.prompt_for_new_name_for_city_at_cursor()
        if ch == 'e':
            self.modify_terrain_at_cursor()
        if ch == 'p':
            self.switch_to_SpecifyPaintbrushTerrainMode()
        if ch == 'f':
            self.cycle_paintbrush_faction()
        if ch == 'w':
            self.switch_to_SpecifyPaintbrushUnitTypeMode()
        if ch == 'd':
            mode = BrowseMapMode()
        if ch == 'c':
            self.add_city_at_cursor()
        if ch == 'a':
            self.add_unit_at_cursor()

    def add_unit_at_cursor(self):
        unit = Unit(paintbrush_faction,paintbrush_unittype,px,py)
        units.append(unit)
        msg('new %s added at %s,%s' % (desc_unit(unit), px, py))

    def is_city_name_used(self, name):
        for c in cities:
            if c.name == name:
                return True
        return False

    def get_name_for_new_city(self):
        linecache.checkcache()
        names = linecache.getlines('city_names')
        names = __builtins__.map(lambda ln: ln.strip(), names) #TODO should only do once per app run, not each call to the enclosing function
        attempts = 0
        unique_ord = 2
        was_unique = True
        while attempts < 200:
            name = random.choice(names)
            if attempts > 100:
                name = '%s %s' % (name, unique_ord)
                unique_ord += 1
            if not self.is_city_name_used(name):
                break
            attempts += 1
        else:
            msg('else reached')
            was_unique = False
        return name, was_unique

    def add_city_at_cursor(self):
        if not get_city_at(px,py):
            name, was_unique = self.get_name_for_new_city()
            city  = City(name,paintbrush_faction,10,px,py)
            cities.append(city)
            msg('city %s added at %s,%s' % (city.name, city.x, city.y))
        else:
            msg('city already there, no more than one allowed')

    def cycle_paintbrush_faction(self):
        global paintbrush_faction
        paintbrush_faction += 1
        if paintbrush_faction >= len(factions.keys()):
            paintbrush_faction = 0

    def get_selectable_factions(self):
        return factions.keys()

    def delete_all_at_cursor(self):
        unitshere = units_at(px,py)
        for u in unitshere:
            msg('deleting unit %s at cursor' % desc_unit(u))
            destroy_unit(u)
        city = get_city_at(px,py)
        if city:
            msg('deleted city %s at cursor' % city.name)
            cities.remove(city)

    def prompt_for_new_name_for_city_at_cursor(self):
        global mode
        city = get_city_at(px,py)
        if city:
            subscr = curses.newwin(1,20,0,0)
            subscr.addstr(0,0,city.name)
            subscr.refresh()
            tp = curses.textpad.Textbox(subscr)
            newname = tp.edit().strip()
            msg('renamed city to %s' % newname)
            city.name = newname

    def modify_terrain_at_cursor(self):
        map[px][py].terr = paintbrush_terrain

    def switch_to_SpecifyPaintbrushTerrainMode(self):
        global mode
        mode = SpecifyPaintbrushTerrainMode(mode)

    def switch_to_SpecifyPaintbrushUnitTypeMode(self):
        global mode
        mode = SpecifyPaintbrushUnitTypeMode(mode)

    def draw_sidebar(self, *args, **kwargs):
        BrowseMapMode.draw_sidebar(self,*args,**kwargs)
        addstr(2,mapw+15,'brush:')
        attr = curses.color_pair(type2terr[paintbrush_terrain].color)
        addstr(2,mapw+15+7,'%s' % type2terr[paintbrush_terrain].char,attr)
        attr = curses.color_pair(factions[paintbrush_faction].color)
        addstr(2,mapw+15+7+2,'%s' % factions[paintbrush_faction].name[0],attr)
        addstr(2,mapw+15+7+2+2,'%s' % unittypes[paintbrush_unittype].char)

class SpecifyCityBuildTypeMode(Mode):
    name = 'Specify Build Type'

    def __init__(self, city):
        self.city = city

    def handle_getch(self, ch):
        global mode
        for utid in unittypes:
            type = unittypes[utid]
            if type.buildchar == ch:
                self.city.buildtype = utid
                self.city.building = True
                msg('city %s now building %s' % (self.city.name, type.name))
                break
        else:
            msg('no unit type associated with that char')
        mode = BrowseMapMode()

class SpecifyPaintbrushTerrainMode(Mode):
    name = 'Specify Brush Terrain'

    def __init__(self, prevmode):
        Mode.__init__(self)
        self.prevmode = prevmode

    def handle_getch(self, ch):
        global mode, paintbrush_terrain
        for terrid in type2terr:
            terr = type2terr[terrid]
            if terr.char == ch:
                paintbrush_terrain = terrid
                msg('changed terrain paintbrush to %s (%s)' % (terr.name, terr.char))
                break
        else:
            msg('unrecognized terrain char, no terrain paintbrush change made')
        mode = self.prevmode

class SpecifyPaintbrushUnitTypeMode(Mode):
    name = 'Specify Brush Unit Type'

    def __init__(self, prevmode):
        Mode.__init__(self)
        self.prevmode = prevmode

    def handle_getch(self, ch):
        global mode, paintbrush_unittype
        for utid in unittypes:
            type = unittypes[utid]
            if type.buildchar == ch:
                paintbrush_unittype = utid
                msg('brush unit type now %s' % unittypes[utid].name)
                break
        else:
            msg('no unit type associated with that char')
        mode = self.prevmode

class UnitSelectedMode(Mode):
    name = 'Unit Selected'
    return_mode_class = BrowseMapMode

    def __init__(self, unit, selectable_factions):
        self.unit = unit
        self.selectable_factions = selectable_factions

    def handle_getch(self, ch):
        if ch == 'i':
            self.move_sel_unit(0,-1)
        if ch == 'u':
            self.move_sel_unit(-1,-1)
        if ch == 'o':
            self.move_sel_unit(1,-1)
        if ch == 'm':
            self.move_sel_unit(0,1)
        if ch == 'n':
            self.move_sel_unit(-1,1)
        if ch == ',':
            self.move_sel_unit(1,1)
        if ch == 'j':
            self.move_sel_unit(-1,0)
        if ch == 'k':
            self.move_sel_unit(1,0)
        if ch == 'D':
            self.disband_selected_unit()
        if ch == '.':
            self.cycle_sel_unit_in_same_cell()
        if ch == ' ':
            self.unselect_unit()

    def refresh_display(self):
        scr.erase()
        draw_panel_borders()
        draw_map()
        draw_unit_at(self.unit, self.unit.y, self.unit.x)
        draw_messages()
        self.draw_sidebar([self.unit,])
        put_cursor_at_active_unit()
        scr.refresh()

    def disband_selected_unit(self):
        msg('disbanded %s' % desc_unit(self.unit))
        destroy_unit(self.unit)
        self.unselect_unit() 

    def unselect_unit(self):
        global mode
        #mode = BrowseMapMode()
        mode = self.return_mode_class()
        #mode.refresh_display()

    def cycle_sel_unit_in_same_cell(self):
        if len(units) > 0:
            foundPrev = False
            i = 0
            while True:
                u = units[i]
                if u.x == self.unit.x and u.y == self.unit.y and u.owner in self.selectable_factions:
                    if foundPrev:
                        self.unit = u
                        return
                    else:
                        if u == self.unit:
                            foundPrev = True
                if i == len(units)-1:
                    i = 0
                else:
                    i += 1

    def move_sel_unit(self, xrel, yrel):
        global py, px
        if self.unit.moveleft < 1:
            msg('the unit does not have enough move left this turn')
            return
        nx = self.unit.x + xrel
        ny = self.unit.y + yrel
        nx,ny = force_valid_coords(nx,ny)
        if nx == self.unit.x and ny == self.unit.y:
            return
        if is_enemy_unit_there(self.unit.owner,nx,ny):
            self.unit.moveleft -= 1
            at = self.unit
            df = get_enemy_unit_there_to_attack(at.owner,nx,ny)
            atktype = unittypes[at.type]
            deftype = unittypes[df.type]
            # determine which attack type is best against the defender:
            # soft (infantry-style weapons like pistols, rifles and MG)? or hard (armor/tank/anti-tank/AP/missile) weapons?
            softchance = float(atktype.softatk) / float(atktype.softatk + deftype.softdef)
            hardchance = float(atktype.hardatk) / float(atktype.hardatk + deftype.harddef)
            besttype = (hardchance > softchance) and 'hard' or 'soft'
            bestchance = hardchance
            if besttype == 'soft':
                bestchance = softchance
            atktypedesc = '(%s %.4s)' % (besttype, bestchance)
            if rand_success(bestchance):
                df.hp -= 1
                if df.hp <= 0:
                    msg('%s attacked %s and destroyed %s' % (desc_unit(at), atktypedesc, desc_unit(df)))
                    destroy_unit(df)
                else:
                    msg('%s attacked %s and damaged %s' % (desc_unit(at), atktypedesc, desc_unit(df)))
            else:
                msg('%s attacked %s but failed to damage %s' % (desc_unit(at), atktypedesc, desc_unit(df)))
            return
        if type2terr[map[nx][ny].terr].impassable:
            msg('%s terrain there blocks movement' % type2terr[map[nx][ny].terr].name)
            return
        self.unit.moveleft -= 1
        self.unit.x = nx
        self.unit.y = ny
        px = nx
        py = ny
        for c in cities:
            if c.x == nx and c.y == ny and c.owner != self.unit.owner:
                c.owner = self.unit.owner
                c.building = True
                msg('city %s captured by %s' % (c.name, desc_unit(self.unit)))

#TODO: fast workaround of issue caused by UnitSelectedMode not being defined at time I'm defining BrowseMapMode
BrowseMapMode.unit_selected_mode = UnitSelectedMode

class EditorUnitSelectedMode(UnitSelectedMode):
    name = 'Unit Selected in Editor'
    return_mode_class = EditorMode

    def handle_getch(self, ch):
        UnitSelectedMode.handle_getch(self,ch)

    def move_sel_unit(self, xrel, yrel):
        global px, py
        nx = self.unit.x + xrel
        ny = self.unit.y + yrel
        nx,ny = force_valid_coords(nx,ny)
        if nx == self.unit.x and ny == self.unit.y:
            return
        self.unit.x = nx
        self.unit.y = ny
        px = nx
        py = ny

#TODO quick workaround to class definition order issue
EditorMode.unit_selected_mode = EditorUnitSelectedMode

class GameOverMode(BrowseMapMode):
    name = 'Game Over'

    def __init__(self):
        BrowseMapMode.__init__(self)
        self.disabled_keys['b'] = True
        self.disabled_keys['t'] = True

    def handle_getch(self, ch):
        retval = BrowseMapMode.handle_getch(self,ch)
        if retval is not None and not retval:
            return False
        if ch == 'r':
            restart_game()

    def post_handle_getch(self):
        pass # so no victory_check() performed


def fill_terrain(terr, x, y, w, h):
    for xx in range(x,x+w):
        for yy in range(y,y+h):
            if is_valid_xy(xx,yy):
                map[xx][yy].terr = terr

def splash_terrain(terr, x, y, dx, dy, nmin, limit, maxdepth=100, depth=0, sofar=0):
    depth += 1
    if depth > maxdepth:
        return sofar, depth
    if is_valid_xy(x,y):
        map[x][y].terr = terr
        sofar += 1
    if sofar >= limit:
        return sofar, depth
    minbase = min(nmin-sofar, 1)
    n = rand_range(minbase,5)
    for i in range(n):
        if chance(3,4):
            pass
        else:
            odx = dx
            ody = dy
            dx,dy = rand_diff(2,2)
            dx = dx + odx
            dy = dy + ody
        nx = x + dx
        ny = y + dy
        sofar, depth = splash_terrain(terr,nx,ny,dx,dy,nmin,limit,maxdepth,depth,sofar)
        if sofar >= limit: break
    return sofar, depth

def place_units_around(owner, type, x, y, dxm, dym, nmin, nmax):
    n = rand_range(nmin, nmax-nmin)
    for i in range(n):
        dx,dy = rand_diff(2,2)
        xx,yy = force_valid_coords(x+dx, y+dy)
        u = Unit(owner,type,xx,yy)
        units.append(u)

def reset_world():
    global px, py, mapw, maph, map, factions, units, cities, msgs, curfac, paintbrush_terrain

    px = 10
    py = 10
    mapw = 50
    maph = 30

    msgs = []

    map = []
    for x in range(mapw):
        col = []
        for y in range(maph):
            col.append(Cell())
        map.append(col)
    map[1][1].terr = 1
    map[2][1].terr = 2
    fill_terrain(2, 30, 20, 50, 30)
    fill_terrain(0, 45, 30, 20, 20)
    fill_terrain(1, 50, 35, 20, 20)
    splash_terrain(1,5,8,1,0,3,10)
    splash_terrain(1,10,12,1,0,3,5)
    splash_terrain(1,15,18,1,0,8,20)

    factions = {
        0 : Faction('Neutral',1),
        1 : Faction('Blue',2),
        2 : Faction('Red',3),
        3 : Faction('Green',4)}

    bluecap  = City('BlueCap',   1, 10,  5,  5)
    redcap   = City('RedCap',    2, 10, 15, 10)
    greencap = City('GreenCap',  3, 10, 25, 15)

    cities = [
        bluecap,
        redcap,
        greencap,
        City('Paris',  0, 10,  7, 20),
        City('Denver', 0, 10, 12,  5)]

    # all non-neutral cities should be building
    for c in cities:
        if c.owner > 0:
            c.building = True

    units = [
        Unit(1,0,bluecap.x+1,bluecap.y+1),
        Unit(1,1,bluecap.x+2,bluecap.y-1),

        Unit(2,0,bluecap.x+3,bluecap.y-1),
        Unit(2,1,bluecap.x+2,bluecap.y-2),

        Unit(2,0,redcap.x+1,redcap.y-1),
        Unit(2,0,redcap.x-1,redcap.y+2),
        Unit(2,0,redcap.x,redcap.y+1),

        Unit(3,2,greencap.x,greencap.y-1)]

    c = city_with_name('Paris')
    place_units_around(c.owner, type_for_name('partisans'), c.x, c.y, 3, 3, 3, 5)

    px = mapw / 2
    py = maph / 2

    turn = 1
    curfac = 1

    paintbrush_terrain = terrname2id('mountains')

    msg('%s' % gamename)
    msg('by Mike Kramlich for ZodLogic Games')

def restart_game():
    global mode
    reset_world()
    mode = BrowseMapMode()

def victory_check():
    global mode
    fac_has_forces = {}
    for f in factions:
        fac_has_forces[f] = False
    for u in units:
        fac_has_forces[u.owner] = True
    for c in cities:
        fac_has_forces[c.owner] = True
    #for f in factions:
        #msg('fac %s has forces: %s' % (factions[f].name, fac_has_forces[f]))
    survivors = []
    for f in fac_has_forces:
        if fac_has_forces[f]:
            survivors.append(f)
    if len(survivors) == 1:
        msg('VICTORY for %s' % factions[survivors[0]].name)
        msg('GAME OVER')
        msg("PRESS 'R' TO RESTART")
        mode = GameOverMode()

def init(stdscr, *args):
    global scr, mode

    scr = stdscr
    curses.start_color() 
    curses.init_pair(1, curses.COLOR_WHITE,  curses.COLOR_BLACK)
    curses.init_pair(2, curses.COLOR_WHITE,  curses.COLOR_BLUE)
    curses.init_pair(3, curses.COLOR_WHITE,  curses.COLOR_RED)
    curses.init_pair(4, curses.COLOR_WHITE,  curses.COLOR_GREEN)
    curses.init_pair(5, curses.COLOR_BLACK,  curses.COLOR_YELLOW)
    curses.init_pair(6, curses.COLOR_WHITE,  curses.COLOR_BLACK)
    curses.init_pair(7, curses.COLOR_BLUE,   curses.COLOR_BLACK)
    curses.init_pair(8, curses.COLOR_YELLOW, curses.COLOR_BLACK)
    curses.init_pair(9, curses.COLOR_BLACK,  curses.COLOR_MAGENTA) # highlight

    min_req_w = mapw + 5
    min_req_h = maph + 5
    if scr.getmaxyx()[1] < min_req_w or scr.getmaxyx()[0] < min_req_h:
        raise 'terminal window size must be at least %s cols by %s lines!' % (min_req_w, min_req_h)

    restart_game()

    sys_argv = args[0]
    if len(sys_argv) >= 2:
        if sys_argv[1] == 'new':
            pass
        else:
            save_fname = sys_argv[1]
            load(save_fname)
    else:
        load()

    mode.refresh_display()

    while True:
        ch = chr(scr.getch())
        retval = mode.handle_getch(ch)
        if retval is not None and not retval: # is it False but not None?
            break
        mode.post_handle_getch()
        mode.refresh_display()

if __name__ == '__main__':
    curses.wrapper(init, sys.argv)
