--[[
    Tien's Weapon Inspection - the timed action.

    A deliberately plain ISBaseTimedAction. It changes nothing about the weapon and
    nothing about the world: the only thing it produces is a window, and it produces it
    on the machine that queued the action.

    Multiplayer needs no code here. setActionAnim() sets the PerformingAction character
    variable, which puts the player into PlayerActionsState, and the engine sends that
    state - the action name and the models in each hand - to the server in a StatePacket
    the moment the local player enters it. The server relays it and every other client
    plays the same animation node out of this mod's AnimSets folder. Sending a command of
    our own alongside that would only make a second machine try to start the same
    animation twice. See docs/implementation.md.
]]

require "TimedActions/ISBaseTimedAction"
require "TienInspectWeapon/InspectWeapon_Shared"

local IW = TienInspectWeapon

ISTienInspectWeaponAction = ISBaseTimedAction:derive("ISTienInspectWeaponAction")

-- Held, not merely owned. Dropping the weapon, swapping hands or having it knocked away
-- mid-look should end the look, and getting the item back out of the inventory by ID is
-- what makes that check survive a multiplayer client rebuilding its item objects.
function ISTienInspectWeaponAction:isValid()
    if not self.character or self.character:isDead() then return false end
    if not self.weapon then return false end

    local held = IW.findWeapon(self.character)
    if not held then return false end
    return held:getID() == self.weapon:getID()
end

function ISTienInspectWeaponAction:start()
    if isClient() then
        -- On a client the object handed to :new may be a stale copy; take the live one.
        local current = self.character:getInventory():getItemById(self.weapon:getID())
        if current then self.weapon = current end
    end

    -- No setOverrideHandModels call on purpose. The weapon is already in the character's
    -- hands and is exactly what should be on screen; overriding would swap the model out
    -- for the same model and cost a needless re-equip on every client.
    self:setActionAnim(IW.ACTION_ANIM)
end

function ISTienInspectWeaponAction:update()
    self.character:setMetabolicTarget(Metabolics.LightDomestic)
end

function ISTienInspectWeaponAction:complete()
    -- The window belongs to whoever did the looking. On a co-op host this action can run
    -- for a second player on the same machine, so the window is opened for the player
    -- number that owns the character rather than for player zero.
    if self.character:isLocalPlayer() and ISTienInspectWeaponWindow then
        ISTienInspectWeaponWindow.open(self.character, self.weapon)
    end
    return true
end

function ISTienInspectWeaponAction:getDuration()
    if self.character:isTimedActionInstant() then return 1 end

    local seconds = IW.opt("InspectSeconds", 2.5)
    if type(seconds) ~= "number" or seconds <= 0 then seconds = 2.5 end

    -- The sandbox option is in seconds; the engine counts in its own units.
    local duration = seconds * IW.TICKS_PER_SECOND

    -- A firearm has more to check over than a kitchen knife, and someone who knows
    -- weapons checks faster. Maintenance is the skill the game already ties to looking
    -- after a weapon, so it is the one that pays here: a quarter off at level ten.
    if self.weapon and self.weapon:isRanged() then
        duration = duration * 1.25
    end
    local maintenance = self.character:getPerkLevel(Perks.Maintenance) or 0
    duration = duration * (1 - 0.025 * maintenance)

    -- ISBaseTimedAction:adjustMaxTime multiplies this again for unhappiness, drink,
    -- wounded hands and body temperature, so the sandbox figure is the baseline for a
    -- healthy character rather than a promise.
    return duration
end

function ISTienInspectWeaponAction:new(character, weapon)
    local o = ISBaseTimedAction.new(self, character)
    o.character = character
    o.weapon = weapon

    -- Looking at something is not work. It costs no calories worth counting and a hurt
    -- hand does not slow down looking, so the vanilla wounded-hands penalty is skipped.
    o.ignoreHandsWounds = true
    o.caloriesModifier = 0

    -- Moving, running or raising the weapon all mean the player has stopped looking at it.
    o.stopOnWalk = true
    o.stopOnRun = true
    o.stopOnAim = true

    o.maxTime = o:getDuration()
    return o
end
