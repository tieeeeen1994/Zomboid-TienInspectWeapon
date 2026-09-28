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

-- Where each player last left their window, by player number: the screen point the window's
-- anchor was at, and which anchor that was. Written on close and read on open, which is what
-- makes a window the player dragged somewhere come back there.
ISTienInspectWeaponWindow.placement = {}

-- The anchor point each player chose from the gear menu, by player number. Not keyed by
-- resolution: it is a preference about how the window behaves, not about where it is.
ISTienInspectWeaponWindow.anchors = {}

--[[
    Anchor points.

    The anchor is the point of the window that stays still. The window is sized from the
    weapon every frame, and a firearm with eight rows is a good deal taller than a kitchen
    knife with three, so something has to stay put while it grows and shrinks; the anchor
    is that point. It is also what gets remembered, so a window opening at a different size
    from last time puts the same point back where the player left it.

    fx and fy are the anchor's place across and down the window, 0 to 1. Bottom centre is
    the default because the window starts out above the hotbar: holding its bottom edge
    keeps every weapon the same distance off the hotbar instead of the tall ones growing
    down over it.
]]
ISTienInspectWeaponWindow.ANCHORS = {
    { key = "TL", fx = 0,   fy = 0 },
    { key = "T",  fx = 0.5, fy = 0 },
    { key = "TR", fx = 1,   fy = 0 },
    { key = "L",  fx = 0,   fy = 0.5 },
    { key = "C",  fx = 0.5, fy = 0.5 },
    { key = "R",  fx = 1,   fy = 0.5 },
    { key = "BL", fx = 0,   fy = 1 },
    { key = "B",  fx = 0.5, fy = 1 },
    { key = "BR", fx = 1,   fy = 1 },
}
local DEFAULT_ANCHOR = "B"

local anchorByKey = {}
for _, a in ipairs(ISTienInspectWeaponWindow.ANCHORS) do
    anchorByKey[a.key] = a
end

local function anchorFor(key)
    return anchorByKey[key] or anchorByKey[DEFAULT_ANCHOR]
end

--[[
    Remembering the position across sessions.

    A small file in the Zomboid folder, next to the game's own layout.ini, which is the
    model for this: a UI preference belongs to the person at the keyboard, not to the save
    and not to the server, so it does not go in ModData.

    Positions are keyed by resolution, again following layout.ini. A position that sits
    neatly above the hotbar at 1920x1080 is somewhere else entirely at 1280x720, and a
    player who switches between the two should find the window where they left it in each
    rather than having one clobber the other. Lines for resolutions other than the current
    one are carried through a rewrite untouched, which is what makes that work.

    Three kinds of line:

        <width>x<height> <playerNum> <x> <y> <anchor>   where that anchor point was left
        <width>x<height> <playerNum> <x> <y>            the same, from before anchors
                                                        existed: always bottom centre
        anchor <playerNum> <anchor>                     the anchor chosen in the gear menu
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
    ISTienInspectWeaponWindow.anchors = {}
    foreignLines = {}

    local reader = getFileReader(PLACEMENT_FILE, true)
    if not reader then return end
    while true do
        local raw = reader:readLine()
        if raw == nil then break end

        local line = string.trim(raw)
        if line ~= "" and string.sub(line, 1, 1) ~= "#" then
            local f = string.split(line, " ")
            if #f == 3 and f[1] == "anchor" then
                local num = tonumber(f[2])
                if num and anchorByKey[f[3]] then
                    ISTienInspectWeaponWindow.anchors[num] = f[3]
                end
            elseif #f == 4 or #f == 5 then
                if f[1] == mine then
                    local num, x, y = tonumber(f[2]), tonumber(f[3]), tonumber(f[4])
                    local anchor = f[5] or DEFAULT_ANCHOR
                    if num and x and y and anchorByKey[anchor] then
                        ISTienInspectWeaponWindow.placement[num] = { x = x, y = y, anchor = anchor }
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

    writer:write("# Tien's Weapon Inspection - remembered window position and anchor.\r\n")
    writer:write("# <width>x<height> <playerNum> <x> <y> <anchor>\r\n")
    writer:write("# anchor <playerNum> <anchor>\r\n")

    for num, key in pairs(ISTienInspectWeaponWindow.anchors) do
        writer:write(string.format("anchor %d %s\r\n", num, key))
    end

    for _, line in ipairs(foreignLines) do
        writer:write(line .. "\r\n")
    end

    local mine = resolutionKey()
    for num, p in pairs(ISTienInspectWeaponWindow.placement) do
        -- Rounded rather than passed straight to %d: these are screen coordinates arrived
        -- at by halving a width, so they are routinely fractional.
        writer:write(string.format("%s %d %d %d %s\r\n", mine, num,
            math.floor(p.x + 0.5), math.floor(p.y + 0.5), p.anchor))
    end

    writer:close()
end

-- The load has to happen before the write, and not only so that other resolutions' lines
-- survive the rewrite: a load triggered by a resolution change clears the table, so doing
-- it after would throw away the position that was just recorded. Keeping both calls in one
-- place is what stops that ordering being got wrong again.
local function rememberPlacement(playerNum, x, y, anchor)
    loadPlacement()
    ISTienInspectWeaponWindow.placement[playerNum] = { x = x, y = y, anchor = anchor }
    savePlacement()
end

local function rememberAnchor(playerNum, anchor)
    loadPlacement()
    ISTienInspectWeaponWindow.anchors[playerNum] = anchor
    savePlacement()
end

-- Every resolution's position for this player, not only the current one's: "reset" means
-- back to the default spot, and a player who resets at one resolution and then switches
-- would not expect to find the old position waiting at the other. The anchor choice stays;
-- it is a setting, not a position.
local function forgetPlacement(playerNum)
    loadPlacement()
    ISTienInspectWeaponWindow.placement[playerNum] = nil
    local kept = {}
    for _, line in ipairs(foreignLines) do
        local f = string.split(line, " ")
        if tonumber(f[2]) ~= playerNum then
            table.insert(kept, line)
        end
    end
    foreignLines = kept
    savePlacement()
end

local function savedAnchor(playerNum)
    loadPlacement()
    return ISTienInspectWeaponWindow.anchors[playerNum] or DEFAULT_ANCHOR
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

-- The window's default spot, as the bottom centre it should have: just above the hotbar,
-- because that is already where the player is looking when they are thinking about what
-- is in their hands, and because it leaves the middle of the screen - the part with the
-- zombies in it - alone. The same spot whichever anchor is chosen; the anchor decides how
-- the window grows from there.
local function defaultBottomCentre(playerNum)
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

-- A position is no use if the window lands off the edge, because there is no title bar
-- left to drag it back by. Going fullscreen or changing resolution between one inspection
-- and the next is enough to do it, and so is a window near an edge growing towards it.
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

--[[
    Keeping the anchor still.

    anchorX, anchorY is where the anchor point is meant to be, in screen coordinates, and
    placedX, placedY is where this code last put the window. Kept apart from the window's
    actual position because clamping can push the window off its anchor: a window near the
    bottom edge that grows is pushed up, and when it shrinks again it should come back down
    to the anchor rather than stay pushed.

    The window having moved since it was last placed means the player dragged it, and then
    the anchor goes with it - measured afresh off the window where it now is.
]]
function ISTienInspectWeaponWindow:anchorPoint()
    if self.anchorX == nil or self:getX() ~= self.placedX or self:getY() ~= self.placedY then
        local a = anchorFor(self.anchorKey)
        self.anchorX = self:getX() + self:getWidth() * a.fx
        self.anchorY = self:getY() + self:getHeight() * a.fy
        self.placedX, self.placedY = self:getX(), self:getY()
    end
    return self.anchorX, self.anchorY
end

-- Puts the window's anchor point at ax, ay, then keeps it on screen.
function ISTienInspectWeaponWindow:placeAnchor(ax, ay)
    local a = anchorFor(self.anchorKey)
    self:setX(ax - self:getWidth() * a.fx)
    self:setY(ay - self:getHeight() * a.fy)
    clampToScreen(self, self.playerNum)
    self.anchorX, self.anchorY = ax, ay
    self.placedX, self.placedY = self:getX(), self:getY()
end

-- Resizes around the anchor: measure where it is at the old size, resize, put it back.
function ISTienInspectWeaponWindow:resizeAnchored(width, height)
    local ax, ay = self:anchorPoint()
    self:setWidth(width)
    self:setHeight(height)
    self:placeAnchor(ax, ay)
end

-- Places the window so that the anchor `key` sits at x, y, then takes the window's own
-- anchor from where that leaves it. That is how a position recorded under one anchor - a
-- line from before anchors existed, or the default spot, which is a bottom centre - is
-- honoured by a window set to another.
function ISTienInspectWeaponWindow:placeBy(key, x, y)
    local a = anchorFor(key)
    self:setX(x - self:getWidth() * a.fx)
    self:setY(y - self:getHeight() * a.fy)
    self.anchorX = nil
    local ax, ay = self:anchorPoint()
    self:placeAnchor(ax, ay)
end

-- Where the window goes when it opens: where the player last left it, or failing that the
-- default spot above the hotbar. Called after layout, because placing by anchor needs the
-- size the weapon's rows gave the window.
function ISTienInspectWeaponWindow:placeOnOpen()
    loadPlacement()
    local remembered = ISTienInspectWeaponWindow.placement[self.playerNum]
    if remembered then
        self:placeBy(remembered.anchor, remembered.x, remembered.y)
    else
        self:placeDefault()
    end
end

function ISTienInspectWeaponWindow:placeDefault()
    local x, y = defaultBottomCentre(self.playerNum)
    self:placeBy("B", x, y)
end

--[[ The gear menu ]]

function ISTienInspectWeaponWindow:setAnchor(key)
    if not anchorByKey[key] then return end
    self.anchorKey = key
    -- Measured afresh for the new anchor off the window as it is now, so choosing one does
    -- not move the window; it only changes which point holds still from here on.
    self.anchorX = nil
    self:anchorPoint()
    rememberAnchor(self.playerNum, key)
end

function ISTienInspectWeaponWindow:resetPosition()
    forgetPlacement(self.playerNum)
    self:placeDefault()
end

function ISTienInspectWeaponWindow:onGearButton()
    local x = self:getAbsoluteX() + self.gearButton:getX()
    local y = self:getAbsoluteY() + self.gearButton:getBottom()
    local context = ISContextMenu.get(self.playerNum, x, y)

    local anchorOption = context:addOption(getText("IGUI_TienInspectWeapon_AnchorPoint"))
    local tip = ISWorldObjectContextMenu.addToolTip()
    tip.description = getText("IGUI_TienInspectWeapon_AnchorPoint_tooltip")
    anchorOption.toolTip = tip

    local sub = ISContextMenu:getNew(context)
    context:addSubMenu(anchorOption, sub)
    for _, a in ipairs(ISTienInspectWeaponWindow.ANCHORS) do
        local option = sub:addOption(getText("IGUI_TienInspectWeapon_Anchor_" .. a.key), self,
            ISTienInspectWeaponWindow.setAnchor, a.key)
        sub:setOptionChecked(option, a.key == self.anchorKey)
    end

    local resetOption = context:addOption(getText("IGUI_TienInspectWeapon_ResetPosition"), self,
        ISTienInspectWeaponWindow.resetPosition)
    local resetTip = ISWorldObjectContextMenu.addToolTip()
    resetTip.description = getText("IGUI_TienInspectWeapon_ResetPosition_tooltip")
    resetOption.toolTip = resetTip
end

-- A gear in the title bar, just left of the collapse button, drawn and built the way the
-- chat window builds its own: vanilla's inventory-pane gear, no border or background, and
-- anchored to the right edge so it follows the window as layout widens it.
function ISTienInspectWeaponWindow:createChildren()
    ISCollapsableWindow.createChildren(self)
    self:setResizable(false)

    local buttonHeight = self:titleBarHeight() - 2
    local buttonOffset = 1 + (5 - getCore():getOptionFontSizeReal()) * 2
    self.gearButton = ISButton:new(self.width - buttonHeight * 2 - buttonOffset - 1, 1,
        buttonHeight, buttonHeight, "", self, ISTienInspectWeaponWindow.onGearButton)
    self.gearButton.anchorRight = true
    self.gearButton.anchorLeft = false
    self.gearButton:initialise()
    self.gearButton.borderColor.a = 0.0
    self.gearButton.backgroundColor.a = 0
    self.gearButton.backgroundColorMouseOver.a = 0
    self.gearButton:setImage(getTexture("media/ui/inventoryPanes/Button_Gear.png"))
    self.gearButton.tooltip = getText("IGUI_TienInspectWeapon_Settings")
    self:addChild(self.gearButton)
end

-- The window follows the weapon, not the other way round: lose the weapon and it closes.
-- That keeps it honest about what it is describing and saves the player dismissing it.
--
-- This is the same in Persistent mode. There no action closes the window, but the weapon
-- leaving the character's hands still does: a window about a weapon that has been put
-- away, dropped or swapped for another is describing something the player is no longer
-- holding.
--
-- Easy mode turns it round. The window is not about one weapon but about the character's
-- hands, so it never closes itself: it describes whatever is held now, switching as weapons
-- are swapped, and says the hands are empty when they are. An inspectable weapon that has
-- nothing to report gets IW.inspect's own NothingToReport line, as in the other modes.
function ISTienInspectWeaponWindow:refresh()
    if self.mode == IW.MODE_EASY then
        local held = IW.findWeapon(self.character)
        self.weapon = held
        self.weaponID = held and held:getID() or nil
        if held then
            self.rows = IW.inspect(held, self.character)
        else
            self.rows = {
                { kind = "note", text = getText("IGUI_TienInspectWeapon_NoWeapon"), warn = false },
            }
        end
        return true
    end

    local held = IW.findWeapon(self.character)
    if not held or held:getID() ~= self.weaponID then
        self.weapon = nil
        return false
    end

    self.weapon = held
    self.rows = IW.inspect(held, self.character)
    return true
end

function ISTienInspectWeaponWindow:layout()
    local rows = self.rows or {}

    -- The header - icon and name - only exists while there is a weapon to show, which in
    -- every mode but Easy is always.
    local h = self:titleBarHeight() + PAD
    if self.weapon then
        h = h + headerHeight() + PAD
    end
    for _, row in ipairs(rows) do
        h = h + rowHeight(row)
    end
    local height = h + PAD

    -- Wide enough for the longest thing in it. A row is a label on the left and a value
    -- on the right, so the width it needs is both of them plus a gap that keeps them
    -- from touching; a long weapon name or a translation into a wordier language then
    -- widens the window instead of running off the end of it.
    local width = MIN_WIDTH

    if self.weapon then
        width = math.max(width,
            PAD + ICON + PAD + textWidth(UIFont.Medium, self.weapon:getName()) + PAD)
    end

    -- A bar row's label and numbers share the line above its bar the same way, so both
    -- kinds of row measure alike.
    for _, row in ipairs(rows) do
        local left = row.label and textWidth(UIFont.Small, row.label) or 0
        local right = row.text and textWidth(UIFont.Small, row.text) or 0
        width = math.max(width, PAD + left + GAP * 2 + right + PAD)
    end

    -- Resized around the anchor point, so the point the player chose stays where it is and
    -- the rest of the window moves to fit. Only on a change: every frame measures, and a
    -- resize that is not one would still re-place the window and undo a drag in progress.
    if width ~= self.width or height ~= self.height then
        self:resizeAnchored(width, height)
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
    if not weapon and self.mode ~= IW.MODE_EASY then return end

    local y = self:titleBarHeight() + PAD

    --[[ Header: the weapon's own icon and its name ]]

    if weapon then
        local texture = weapon:getTex()
        if texture then
            self:drawTextureScaledAspect(texture, PAD, y, ICON, ICON, 1, 1, 1, 1)
        end

        local textX = PAD + ICON + PAD
        self:drawText(weapon:getName(), textX,
            y + (headerHeight() - fontHeight(UIFont.Medium)) / 2, 1, 1, 1, 1, UIFont.Medium)

        y = y + headerHeight() + PAD
    end

    --[[ Rows ]]

    local barX = PAD
    local barW = self.width - PAD * 2

    for _, row in ipairs(self.rows) do
        if row.kind == "bar" then
            local r, g, b = IW.colorFor(row.fraction, row.inverted)

            self:drawText(row.label, barX, y, 0.86, 0.86, 0.86, 1, UIFont.Small)
            if row.text then
                self:drawText(row.text, barX + barW - textWidth(UIFont.Small, row.text), y,
                    0.80, 0.80, 0.80, 1, UIFont.Small)
            end

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
    -- the anchor point, which is what placeOnOpen reads back, and written to disk now rather
    -- than on a save or quit event, because a player who alt-F4s out of a bad night should
    -- still find the window where they put it.
    local ax, ay = self:anchorPoint()
    rememberPlacement(self.playerNum, ax, ay, self.anchorKey)

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
    o.weaponID = weapon and weapon:getID() or nil
    o.rows = {}
    -- Set by the action once it has started; see close().
    o.action = nil
    -- Which InspectMode opened it; see refresh() and open().
    o.mode = IW.MODE_DEFAULT
    -- The point that holds still as the window resizes, chosen from the gear menu; see
    -- anchorPoint().
    o.anchorKey = savedAnchor(o.playerNum)
    o.anchorX = nil
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

    mode is the InspectMode the window was opened for, IW.MODE_DEFAULT when left out:
    MODE_PERSISTENT from ISTienInspectWeaponPersistentAction, a window no action is tied to
    that the player or the weapon leaving their hands closes, and MODE_EASY straight from
    the key, a window about the hands that only the player closes. Only Easy mode opens
    without a weapon.
]]
function ISTienInspectWeaponWindow.open(character, weapon, mode)
    mode = mode or IW.MODE_DEFAULT
    if not character then return end
    if not weapon and mode ~= IW.MODE_EASY then return end

    local playerNum = character:getPlayerNum()
    local existing = ISTienInspectWeaponWindow.windows[playerNum]

    if existing then
        existing.character = character
        existing.weapon = weapon
        existing.weaponID = weapon and weapon:getID() or nil
        existing.mode = mode
        existing:refresh()
        existing:layout()
        existing:setVisible(true)
        existing:bringToTop()
        return existing
    end

    local window = ISTienInspectWeaponWindow:new(0, 0, character, weapon)
    window.mode = mode
    window:initialise()
    window:addToUIManager()
    window:refresh()
    window:layout()

    -- Placed after layout, not before: the window is sized from the rows the weapon
    -- produced, so its size is not known until refresh and layout have both run, and
    -- placing it by its anchor point needs that size.
    window:placeOnOpen()

    ISTienInspectWeaponWindow.windows[playerNum] = window
    return window
end
