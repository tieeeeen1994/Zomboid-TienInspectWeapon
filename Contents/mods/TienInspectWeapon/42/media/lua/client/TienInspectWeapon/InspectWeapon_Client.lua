--[[
    Tien's Weapon Inspection - client driver.

    Registers the keybinding, decides whether a press can turn into an inspection, and
    queues the timed action. Also adds the same thing to the right-click menu of an
    equipped weapon, because a keybinding nobody has found yet is a mod that does
    nothing.

    Nothing here talks to the server. The action's animation reaches other players
    through the engine's own state replication - see ISTienInspectWeaponAction and
    docs/implementation.md - and the window is this player's alone.
]]

require "TienInspectWeapon/InspectWeapon_Shared"
require "TienInspectWeapon/InspectWeapon_Window"
require "TimedActions/ISTienInspectWeaponAction"

local IW = TienInspectWeapon

--[[ The keybinding ]]

-- A bracketed entry is a section header in the controls options screen; both it and the
-- binding below it are named through UI_optionscreen_binding_* in Translate/EN/UI.json.
-- K is unbound in vanilla Build 42, which is the whole reason it is the default.
local function registerKeyBinding()
    if not keyBinding then return end
    for _, existing in ipairs(keyBinding) do
        if existing.value == IW.KEYBIND then return end
    end
    table.insert(keyBinding, { value = "[Weapon Inspection]" })
    table.insert(keyBinding, { value = IW.KEYBIND, key = Keyboard.KEY_K })
end

registerKeyBinding()

--[[ Whether a press can become an inspection ]]

-- A refusal says why. A hotkey that silently does nothing is indistinguishable from a
-- broken mod.
local function refuse(player, key)
    HaloTextHelper.addBadText(player, getText(key))
end

function IW.canInspect(player)
    if not player or player:isDead() then return false end
    if player:isAsleep() then return false end

    if not IW.findWeapon(player) then
        return false, "IGUI_TienInspectWeapon_NoWeapon"
    end

    -- tooDarkToRead is the engine's own light test and already counts a lit torch in the
    -- off hand, a headlamp, or the room's lights. Vanilla gates its own Inspect option on
    -- this same call and labels the refusal ContextMenu_TooDarkToInspect, so both the
    -- threshold and the wording are the game's rather than ours.
    if player:tooDarkToRead() then
        return false, "ContextMenu_TooDarkToInspect"
    end

    return true
end

function IW.inspectHeldWeapon(player, quiet)
    if not player then return false end

    -- One look at a time, counting both halves: a press during the wind-up must not stack
    -- a second inspection behind the one already running. The hotkey toggles an open
    -- window, so this mainly catches the routes that do not - the context menu, and
    -- another mod calling in.
    if ISTimedActionQueue.hasActionType(player, "ISTienInspectWeaponAction")
        or ISTimedActionQueue.hasActionType(player, "ISTienInspectWeaponHoldAction") then
        return false
    end

    local ok, reason = IW.canInspect(player)
    if not ok then
        if reason and not quiet then refuse(player, reason) end
        return false
    end

    local weapon = IW.findWeapon(player)
    IW.debug("inspecting %s", weapon:getFullType())

    -- Appended, never spliced in front. Reloading or barricading finishes first and the
    -- look happens after; interrupting work the player asked for to show them a window
    -- would be the mod deciding it matters more than what they were already doing.
    ISTimedActionQueue.add(ISTienInspectWeaponAction:new(player, weapon))
    return true
end

--[[ The hotkey ]]

local function onKeyPressed(key)
    if isGamePaused() then return end
    -- Typing "k" into chat is not a request to inspect anything.
    if ISChat and ISChat.focused then return end
    if not getCore():isKey(IW.KEYBIND, key) then return end

    local player = getSpecificPlayer(0)
    if not player then return end

    -- A second press while the window is open puts it away, so one key both opens and
    -- closes and the player never has to reach for the mouse to dismiss it.
    local window = ISTienInspectWeaponWindow.windows[player:getPlayerNum()]
    if window and window:getIsVisible() then
        window:close()
        return
    end

    IW.inspectHeldWeapon(player)
end

--[[ The right-click entry ]]

-- The menu entry deliberately re-finds the weapon rather than acting on the item the
-- menu was built around. A context menu can outlive the state it was opened on, and what
-- this action inspects is whatever is in the character's hands at the moment it starts.
local function onInspectOption(player)
    IW.inspectHeldWeapon(player)
end

local function onFillInventoryContextMenu(playerNum, context, items)
    local player = getSpecificPlayer(playerNum)
    if not player then return end

    local held = IW.findWeapon(player)
    if not held then return end

    -- Only on the weapon that is actually in the character's hands. Offering it on every
    -- weapon in the bag would promise something the action cannot do: it inspects what is
    -- held, and equipping first is the player's decision to make.
    -- An entry in this list is either an InventoryItem or a stack table holding several
    -- of them; unwrapping with instanceof is the idiom vanilla uses everywhere.
    local onHeld = false
    for _, entry in ipairs(items) do
        local item = entry
        if not instanceof(item, "InventoryItem") then item = item.items and item.items[1] end
        if item and item:getID() == held:getID() then
            onHeld = true
            break
        end
    end
    if not onHeld then return end

    context:addOption(getText("ContextMenu_TienInspectWeapon_Inspect"), player, onInspectOption)
end

Events.OnKeyPressed.Add(onKeyPressed)
Events.OnFillInventoryObjectContextMenu.Add(onFillInventoryContextMenu)
