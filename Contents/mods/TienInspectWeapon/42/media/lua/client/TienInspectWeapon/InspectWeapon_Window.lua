--[[
    Tien's Weapon Inspection - the window.

    A small ISCollapsableWindow, one per player number, drawing the rows
    TienInspectWeapon.inspect() read off the weapon - which are the rows the game's own
    tooltip would show, in its order and its wording. It re-reads every frame rather than
    showing a snapshot, so a weapon repaired or sharpened while the window is open
    corrects itself in front of the player instead of lying until it is reopened.

    The window holds the item's ID, not the item. On a multiplayer client the item object
    a player is holding is replaced wholesale when the server sends an update, and a
    window clinging to the old object would draw numbers from a copy nothing else in the
    game agrees with any more.
]]

require "ISUI/ISCollapsableWindow"
require "TienInspectWeapon/InspectWeapon_Shared"

local IW = TienInspectWeapon

ISTienInspectWeaponWindow = ISCollapsableWindow:derive("ISTienInspectWeaponWindow")

-- One window per split-screen player, so two people on one machine do not fight over it.
ISTienInspectWeaponWindow.windows = {}

-- Where each player last left their window, by player number. Written on close and read on
-- open, which is what makes a window the player dragged somewhere come back there.
ISTienInspectWeaponWindow.placement = {}

--[[
    Remembering the position across sessions.

    A small file in the Zomboid folder, next to the game's own layout.ini, which is the
    model for this: a UI preference belongs to the person at the keyboard, not to the save
    and not to the server, so it does not go in ModData.

    Keyed by resolution, again following layout.ini. A position that sits neatly above the
    hotbar at 1920x1080 is somewhere else entirely at 1280x720, and a player who switches
    between the two should find the window where they left it in each rather than having
    one clobber the other. Lines for resolutions other than the current one are carried
    through a rewrite untouched, which is what makes that work.
]]
local PLACEMENT_FILE = "tien-inspect-weapon-window.txt"

local loadedResolution = nil
local foreignLines = {}

local function resolutionKey()
    return getCore():getScreenWidth() .. "x" .. getCore():getScreenHeight()
end

-- Reloads when the resolution changes rather than only once, because the in-memory table
-- belongs to whichever resolution it was read for. Windowing the game between two
-- inspections would otherwise write the old resolution's position under the new one's key
-- and lose both.
local function loadPlacement()
    local mine = resolutionKey()
    if loadedResolution == mine then return end
    loadedResolution = mine

    ISTienInspectWeaponWindow.placement = {}
    foreignLines = {}

    local reader = getFileReader(PLACEMENT_FILE, true)
    if not reader then return end
    while true do
        local raw = reader:readLine()
        if raw == nil then break end

        local line = string.trim(raw)
        if line ~= "" and string.sub(line, 1, 1) ~= "#" then
            -- <width>x<height> <playerNum> <centreX> <bottomY>
            local f = string.split(line, " ")
            if #f == 4 then
                if f[1] == mine then
                    local num, centreX, bottomY = tonumber(f[2]), tonumber(f[3]), tonumber(f[4])
                    if num and centreX and bottomY then
                        ISTienInspectWeaponWindow.placement[num] = {
                            centreX = centreX,
                            bottomY = bottomY,
                        }
                    end
                else
                    table.insert(foreignLines, line)
                end
            end
        end
    end
    reader:close()
end

local function savePlacement()
    local writer = getFileWriter(PLACEMENT_FILE, true, false)
    if not writer then return end

    writer:write("# Tien's Weapon Inspection - remembered window position.\r\n")
    writer:write("# <width>x<height> <playerNum> <centreX> <bottomY>\r\n")

    for _, line in ipairs(foreignLines) do
        writer:write(line .. "\r\n")
    end

    local mine = resolutionKey()
    for num, p in pairs(ISTienInspectWeaponWindow.placement) do
        -- Rounded rather than passed straight to %d: these are screen coordinates arrived
        -- at by halving a width, so they are routinely fractional.
        writer:write(string.format("%s %d %d %d\r\n", mine, num,
            math.floor(p.centreX + 0.5), math.floor(p.bottomY + 0.5)))
    end

    writer:close()
end

-- The load has to happen before the write, and not only so that other resolutions' lines
-- survive the rewrite: a load triggered by a resolution change clears the table, so doing
-- it after would throw away the position that was just recorded. Keeping both calls in one
-- place is what stops that ordering being got wrong again.
local function rememberPlacement(playerNum, centreX, bottomY)
    loadPlacement()
    ISTienInspectWeaponWindow.placement[playerNum] = { centreX = centreX, bottomY = bottomY }
    savePlacement()
end

local PAD = 10
local ICON = 48
local BAR_H = 9
local GAP = 8
local MIN_WIDTH = 290

local function fontHeight(font)
    return getTextManager():getFontHeight(font)
end

local function textWidth(font, text)
    return getTextManager():MeasureStringX(font, text)
end

-- Every height here is measured off the font rather than written down as a pixel count.
-- Project Zomboid's UI font size is a game option, and at the largest setting a row
-- sized for the smallest one puts the label through the bar underneath it.
local function rowHeight(row)
    if row.kind == "bar" then
        return fontHeight(UIFont.Small) + 3 + BAR_H + GAP
    end
    return fontHeight(UIFont.Small) + 4
end

local function headerHeight()
    return math.max(ICON, fontHeight(UIFont.Medium))
end

-- Sat just above the hotbar, because that is already where the player is looking when they
-- are thinking about what is in their hands, and because it leaves the middle of the screen
-- - the part with the zombies in it - alone.
--
-- Anchored by its bottom edge rather than its top, so a wordy firearm with eight rows and a
-- bare kitchen knife with three both sit the same distance off the hotbar instead of one of
-- them growing down into it.
local function defaultAnchor(playerNum)
    -- getPlayerHotbar returns nil before the UI is built, and the hotbar can be switched
    -- off outright. The fallback is the spot the hotbar would have occupied: the game puts
    -- it centred against the bottom edge, so aiming at the same place keeps the window
    -- somewhere sensible either way.
    local hotbar = getPlayerHotbar and getPlayerHotbar(playerNum)
    if hotbar then
        return hotbar:getX() + hotbar:getWidth() / 2, hotbar:getY() - GAP
    end
    return getPlayerScreenLeft(playerNum) + getPlayerScreenWidth(playerNum) / 2,
           getPlayerScreenTop(playerNum) + getPlayerScreenHeight(playerNum) - GAP
end

-- A remembered position is no use if the window lands off the edge, because there is no
-- title bar left to drag it back by. Going fullscreen or changing resolution between one
-- inspection and the next is enough to do it.
local function clampToScreen(window, playerNum)
    local left = getPlayerScreenLeft(playerNum)
    local top = getPlayerScreenTop(playerNum)
    local right = left + getPlayerScreenWidth(playerNum)
    local bottom = top + getPlayerScreenHeight(playerNum)

    local x = math.max(left, math.min(window:getX(), right - window:getWidth()))
    local y = math.max(top, math.min(window:getY(), bottom - window:getHeight()))

    window:setX(x)
    window:setY(y)
end

-- Where the window goes when it opens: where the player last left it, or failing that just
-- above the hotbar, which is already where they are looking when they are thinking about
-- what is in their hands, and which leaves the middle of the screen - the part with the
-- zombies in it - alone.
--
-- Anchored by its bottom edge rather than its top, both here and when remembering. The
-- window is sized from the weapon, so a wordy firearm with eight rows is a good deal taller
-- than a bare kitchen knife; holding the top still would let the tall one grow down over
-- the hotbar, where holding the bottom still keeps every weapon the same distance off it.
local function placeWindow(window, playerNum)
    loadPlacement()

    local remembered = ISTienInspectWeaponWindow.placement[playerNum]
    local centreX, bottomY

    if remembered then
        centreX, bottomY = remembered.centreX, remembered.bottomY
    else
        centreX, bottomY = defaultAnchor(playerNum)
    end

    window:setX(centreX - window:getWidth() / 2)
    window:setY(bottomY - window:getHeight())
    clampToScreen(window, playerNum)
end

function ISTienInspectWeaponWindow:createChildren()
    ISCollapsableWindow.createChildren(self)
    self:setResizable(false)
end

-- The window follows the weapon, not the other way round: lose the weapon and it closes.
-- That keeps it honest about what it is describing and saves the player dismissing it.
function ISTienInspectWeaponWindow:refresh()
    local held = IW.findWeapon(self.character)
    if not held or held:getID() ~= self.weaponID then
        self.weapon = nil
        return false
    end

    self.weapon = held
    self.rows = IW.inspect(held)
    return true
end

function ISTienInspectWeaponWindow:layout()
    local rows = self.rows or {}

    local h = self:titleBarHeight() + PAD + headerHeight() + PAD
    for _, row in ipairs(rows) do
        h = h + rowHeight(row)
    end
    self:setHeight(h + PAD)

    -- Wide enough for the longest thing in it. A row is a label on the left and a value
    -- on the right, so the width it needs is both of them plus a gap that keeps them
    -- from touching; a long weapon name or a translation into a wordier language then
    -- widens the window instead of running off the end of it.
    local width = MIN_WIDTH

    if self.weapon then
        width = math.max(width,
            PAD + ICON + PAD + textWidth(UIFont.Medium, self.weapon:getName()) + PAD)
    end

    for _, row in ipairs(rows) do
        local left = row.label and textWidth(UIFont.Small, row.label) or 0
        -- A bar row is a label over a full-width bar, so only the text rows - a label on
        -- the left and its value on the right - can push the window wider.
        local right = (row.kind ~= "bar" and row.text) and textWidth(UIFont.Small, row.text) or 0
        width = math.max(width, PAD + left + GAP * 2 + right + PAD)
    end

    if width ~= self.width then
        self:setWidth(width)
    end
end

function ISTienInspectWeaponWindow:prerender()
    if not self.character or self.character:isDead() then
        self:close()
        return
    end
    if not self:refresh() then
        self:close()
        return
    end

    self:layout()
    ISCollapsableWindow.prerender(self)
end

function ISTienInspectWeaponWindow:render()
    ISCollapsableWindow.render(self)

    -- Nothing below the title bar exists while collapsed. The base class clips its own
    -- drawing to the title bar with a stencil but clears that stencil on its way out of
    -- render, so anything drawn after this call is drawn unclipped and would sit on the
    -- screen under a window that is supposed to be rolled up.
    if self.isCollapsed then return end

    local weapon = self.weapon
    if not weapon then return end

    local y = self:titleBarHeight() + PAD

    --[[ Header: the weapon's own icon and its name ]]

    local texture = weapon:getTex()
    if texture then
        self:drawTextureScaledAspect(texture, PAD, y, ICON, ICON, 1, 1, 1, 1)
    end

    local textX = PAD + ICON + PAD
    self:drawText(weapon:getName(), textX,
        y + (headerHeight() - fontHeight(UIFont.Medium)) / 2, 1, 1, 1, 1, UIFont.Medium)

    y = y + headerHeight() + PAD

    --[[ Rows ]]

    local barX = PAD
    local barW = self.width - PAD * 2

    for _, row in ipairs(self.rows) do
        if row.kind == "bar" then
            local r, g, b = IW.colorFor(row.ratio)

            self:drawText(row.label, barX, y, 0.86, 0.86, 0.86, 1, UIFont.Small)

            local barY = y + fontHeight(UIFont.Small) + 3
            self:drawRect(barX, barY, barW, BAR_H, 0.55, 0.10, 0.10, 0.10)
            self:drawRect(barX, barY, barW * row.ratio, BAR_H, 0.95, r, g, b)
            self:drawRectBorder(barX, barY, barW, BAR_H, 0.45, 0.55, 0.55, 0.55)

            y = y + rowHeight(row)
        elseif row.kind == "line" then
            self:drawText(row.label, barX, y, 0.86, 0.86, 0.86, 1, UIFont.Small)
            local w = textWidth(UIFont.Small, row.text)
            if row.warn then
                self:drawText(row.text, barX + barW - w, y, 0.85, 0.45, 0.20, 1, UIFont.Small)
            else
                self:drawText(row.text, barX + barW - w, y, 0.80, 0.80, 0.80, 1, UIFont.Small)
            end
            y = y + rowHeight(row)
        else
            -- A sentence on its own line. Amber when it is a fault the player should act
            -- on, plain when it is only stating what the weapon has.
            if row.warn then
                self:drawText(row.text, barX, y, 0.85, 0.45, 0.20, 1, UIFont.Small)
            else
                self:drawText(row.text, barX, y, 0.80, 0.80, 0.80, 1, UIFont.Small)
            end
            y = y + rowHeight(row)
        end
    end
end

-- Closing the window ends the look. The action clears this back-reference before closing
-- the window itself, so the two directions cannot bounce off each other: by the time a
-- close arrives from that side there is no action left here to stop.
function ISTienInspectWeaponWindow:close()
    local action = self.action
    self.action = nil
    if action and action:isStarted() then
        action:forceStop()
    end

    -- Wherever the window has ended up is where the player wants it, so remembering on the
    -- way out catches a drag without this having to know anything about dragging. Stored as
    -- centre and bottom to match how placeWindow reads it back, and written to disk now
    -- rather than on a save or quit event, because a player who alt-F4s out of a bad night
    -- should still find the window where they put it.
    rememberPlacement(self.playerNum,
        self:getX() + self:getWidth() / 2,
        self:getY() + self:getHeight())

    ISTienInspectWeaponWindow.windows[self.playerNum] = nil
    self:setVisible(false)
    self:removeFromUIManager()
end

function ISTienInspectWeaponWindow:onJoypadDown(button)
    if button == Joypad.BButton then
        self:close()
        setJoypadFocus(self.playerNum, nil)
    end
end

function ISTienInspectWeaponWindow:new(x, y, character, weapon)
    local o = ISCollapsableWindow:new(x, y, MIN_WIDTH, 200)
    setmetatable(o, self)
    self.__index = self

    o.character = character
    o.playerNum = character:getPlayerNum()
    o.weapon = weapon
    o.weaponID = weapon:getID()
    o.rows = {}
    -- Set by the action once it has started; see close().
    o.action = nil
    o:setResizable(false)
    o:setTitle(getText("IGUI_TienInspectWeapon_Title"))
    return o
end

--[[
    Opening.

    Reusing the window a player already has open, rather than stacking a new one on top,
    is what makes the hotkey safe to lean on: inspect one weapon, swap, inspect the next,
    and the same window on the same spot answers each time.

    Only a newly created window is positioned, and it goes wherever the last one was left.
    A window already up keeps where it is.
]]
function ISTienInspectWeaponWindow.open(character, weapon)
    if not character or not weapon then return end

    local playerNum = character:getPlayerNum()
    local existing = ISTienInspectWeaponWindow.windows[playerNum]

    if existing then
        existing.character = character
        existing.weapon = weapon
        existing.weaponID = weapon:getID()
        existing:refresh()
        existing:layout()
        existing:setVisible(true)
        existing:bringToTop()
        return existing
    end

    local window = ISTienInspectWeaponWindow:new(0, 0, character, weapon)
    window:initialise()
    window:addToUIManager()
    window:refresh()
    window:layout()

    -- Placed after layout, not before: the window is sized from the rows the weapon
    -- produced, so its height is not known until refresh and layout have both run, and
    -- anchoring the bottom edge needs that height.
    placeWindow(window, playerNum)

    ISTienInspectWeaponWindow.windows[playerNum] = window
    return window
end
