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

function ISTienInspectWeaponWindow:close()
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
    o:setResizable(false)
    o:setTitle(getText("IGUI_TienInspectWeapon_Title"))
    return o
end

--[[
    Opening.

    Reusing the window a player already has open, rather than stacking a new one on top,
    is what makes the hotkey safe to lean on: inspect one weapon, swap, inspect the next,
    and the same window on the same spot answers each time.
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

    -- Centred horizontally, a third of the way down, out of the way of the inventory
    -- panes at the bottom of the screen and of the health panel at the top.
    local x = (getPlayerScreenLeft(playerNum) + getPlayerScreenWidth(playerNum) / 2) - MIN_WIDTH / 2
    local y = getPlayerScreenTop(playerNum) + getPlayerScreenHeight(playerNum) / 3

    local window = ISTienInspectWeaponWindow:new(x, y, character, weapon)
    window:initialise()
    window:addToUIManager()
    window:refresh()
    window:layout()

    ISTienInspectWeaponWindow.windows[playerNum] = window
    return window
end
