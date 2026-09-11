--[[
    Tien's Weapon Inspection - the hold.

    The second half of an inspection. ISTienInspectWeaponAction is the wind-up and queues
    this when it finishes; this opens the window and keeps the character in the inspecting
    pose for as long as the player is reading it.

    Window and hold share one lifetime in both directions. Whatever ends the hold closes
    the window, and closing the window ends the hold.

    Project Zomboid has no action that runs until cancelled - nothing in the game's Lua
    sets an unbounded maxTime - so this is a long countdown with the sandbox ceiling as its
    length rather than a genuinely open-ended state. In practice something almost always
    ends it first.
]]

require "TimedActions/ISBaseTimedAction"
require "TienInspectWeapon/InspectWeapon_Shared"

local IW = TienInspectWeapon

ISTienInspectWeaponHoldAction = ISBaseTimedAction:derive("ISTienInspectWeaponHoldAction")

function ISTienInspectWeaponHoldAction:isValid()
    if not self.character or self.character:isDead() then return false end
    if not self.weapon then return false end

    -- A torch can burn out or a generator die while the window is open.
    if self.character:tooDarkToRead() then
        HaloTextHelper.addBadText(self.character, getText("ContextMenu_TooDarkToInspect"))
        return false
    end

    local held = IW.findWeapon(self.character)
    if not held then return false end
    return held:getID() == self.weapon:getID()
end

function ISTienInspectWeaponHoldAction:start()
    if isClient() then
        local current = self.character:getInventory():getItemById(self.weapon:getID())
        if current then self.weapon = current end
    end

    self:setActionAnim(IW.HOLD_ANIM)

    -- The window belongs to whoever did the looking. On a co-op host this can run for a
    -- second player on the same machine, so it opens for the player number that owns the
    -- character rather than for player zero.
    if self.character:isLocalPlayer() and ISTienInspectWeaponWindow then
        local window = ISTienInspectWeaponWindow.open(self.character, self.weapon)
        if window then window.action = self end
    end
end

function ISTienInspectWeaponHoldAction:update()
    self.character:setMetabolicTarget(Metabolics.LightDomestic)

    -- Yield as soon as the player asks for anything else, rather than making it wait out a
    -- hold measured in tens of seconds. Completing is not the same as failing isValid here:
    -- ISBaseTimedAction.stop calls resetQueue, which would cancel the very action they just
    -- queued behind this one, where completing hands the queue on to it. Vanilla's
    -- WalkToTimedAction ends itself from update the same way.
    local queue = ISTimedActionQueue.getTimedActionQueue(self.character)
    if queue and #queue.queue > 1 then
        self:forceComplete()
    end
end

-- Every exit comes through here - stop(), perform(), and the window closing itself. Clearing the window's back-reference before closing it is
-- what stops the two from calling each other: the window only reaches back for a forceStop
-- while it still believes an action is running.
function ISTienInspectWeaponHoldAction:endLook()
    if not ISTienInspectWeaponWindow then return end
    local window = ISTienInspectWeaponWindow.windows[self.character:getPlayerNum()]
    if not window or window.action ~= self then return end
    window.action = nil
    window:close()
end

function ISTienInspectWeaponHoldAction:stop()
    self:endLook()
    ISBaseTimedAction.stop(self)
end

-- perform(), not complete(), for the reason spelled out on ISTienInspectWeaponAction:perform:
-- a multiplayer client never calls complete(), the server does. The window belongs to this
-- machine, so the call that closes it has to be on a hook this machine runs.
function ISTienInspectWeaponHoldAction:perform()
    self:endLook()
    ISBaseTimedAction.perform(self)
end

-- The server's completion hook, which has nothing to do and only has to succeed.
function ISTienInspectWeaponHoldAction:complete()
    return true
end

-- A ceiling, not a measure of how long looking takes - that is the wind-up's job. Nothing
-- scales this: stretching a ceiling because the character is cold would make the sandbox
-- number mean nothing.
function ISTienInspectWeaponHoldAction:getDuration()
    local seconds = IW.opt("MaxHoldSeconds", 30)
    if type(seconds) ~= "number" or seconds <= 0 then seconds = 30 end
    return seconds * IW.TICKS_PER_SECOND
end

-- Overridden to the identity for the same reason isTimedActionInstant is ignored below:
-- the sandbox number is a ceiling the player chose, and unhappiness or body temperature
-- have no business moving it.
function ISTienInspectWeaponHoldAction:adjustMaxTime(maxTime)
    return maxTime
end

function ISTienInspectWeaponHoldAction:new(character, weapon)
    local o = ISBaseTimedAction.new(self, character)
    o.character = character
    o.weapon = weapon

    o.ignoreHandsWounds = true
    o.caloriesModifier = 0

    o.stopOnWalk = false
    o.stopOnRun = true
    o.stopOnAim = true

    -- No progress circle. It counts down a deadline, and this deadline is a ceiling the
    -- player is not supposed to be racing.
    o.useProgressBar = false

    o.maxTime = o:getDuration()
    return o
end
