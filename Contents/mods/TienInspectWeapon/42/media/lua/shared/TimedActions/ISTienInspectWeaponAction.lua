--[[
    Tien's Weapon Inspection - the timed action.

    A deliberately plain ISBaseTimedAction. It changes nothing about the weapon and
    nothing about the world.

    This is the wind-up, the first half of an inspection: the character brings the weapon
    up and turns it over, on a real countdown with a progress circle, and no window yet.
    When it finishes it queues ISTienInspectWeaponHoldAction, which opens the window and
    holds the pose for as long as the player is reading.

    Splitting it in two is what lets the window arrive a beat after the animation starts
    instead of the instant the key is pressed, and lets each half have its own clip.

    The animation needs no networking code here. setActionAnim() sets the PerformingAction
    character variable, which puts the player into PlayerActionsState, and the engine sends
    that state - the action name and the models in each hand - to the server in a
    StatePacket the moment the local player enters it. The server relays it and every other
    client plays the same animation node out of this mod's AnimSets folder. Sending a
    command of our own alongside that would only make a second machine try to start the
    same animation twice.

    The action's *lifecycle*, on the other hand, is not local in multiplayer at all, and
    which callback the hand-off lives in depends on that. See the comment on perform()
    below, and docs/implementation.md.
]]

require "TimedActions/ISBaseTimedAction"
require "TimedActions/ISTienInspectWeaponHoldAction"
require "TienInspectWeapon/InspectWeapon_Shared"

local IW = TienInspectWeapon

ISTienInspectWeaponAction = ISBaseTimedAction:derive("ISTienInspectWeaponAction")

-- Held, not merely owned. Dropping the weapon, swapping hands or having it knocked away
-- mid-look should end the look, and getting the item back out of the inventory by ID is
-- what makes that check survive a multiplayer client rebuilding its item objects.
function ISTienInspectWeaponAction:isValid()
    if not self.character or self.character:isDead() then return false end
    if not self.weapon then return false end

    -- Checked here and not only at the keypress because the action can sit in the queue
    -- behind something else, and a torch can burn out or a generator die mid-look. Saying
    -- so matches ISReadABook, which announces the same refusal from its own isValid.
    if self.character:tooDarkToRead() then
        HaloTextHelper.addBadText(self.character, getText("ContextMenu_TooDarkToInspect"))
        return false
    end

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

--[[
    The hand-off, and why it is in perform() and not complete().

    complete() is not the client's hook. LuaTimedActionNew.complete() calls the Lua
    complete() only when GameClient.client is false, so on a multiplayer client it is
    never called at all. What happens there instead is that LuaTimedActionNew.start()
    registers the action with ActionManager as a NetTimedAction transaction and sets
    waitForFinished, the server rebuilds the action from the packet by calling
    ISTienInspectWeaponAction:new, and when the server's countdown ends
    NetTimedAction.perform() calls complete() *there*.

    So in multiplayer complete() runs on the server, in a Lua state that has no
    ISTimedActionQueue - that is a client-only file - and no window to open. Queueing the
    hold from complete() meant that in multiplayer the hold was never queued on the
    machine that needed it, which is why the mod played its wind-up and then nothing.

    perform() is called on every machine that runs the action, the client included, which
    is where work belonging to the player's own machine goes. Queueing before
    ISBaseTimedAction.perform keeps the ordering the hand-off relies on: this action is
    still in the queue at that moment, so addToQueue sees a non-zero count and does not
    begin the hold early, and onCompleted then pops this one off and starts it.
]]
function ISTienInspectWeaponAction:perform()
    ISTimedActionQueue.add(ISTienInspectWeaponHoldAction:new(self.character, self.weapon))
    ISBaseTimedAction.perform(self)
end

-- Kept as the server's completion hook. On a multiplayer client this is the call that runs
-- on the server, and all it has to do is succeed: returning false there is how a
-- NetTimedAction reports that it failed.
function ISTienInspectWeaponAction:complete()
    return true
end

function ISTienInspectWeaponAction:getDuration()
    if self.character:isTimedActionInstant() then return 1 end

    local seconds = IW.opt("InspectSeconds", 0.5)
    if type(seconds) ~= "number" or seconds <= 0 then seconds = 0.5 end

    -- The sandbox option is in seconds; the engine counts in its own units.
    local duration = seconds * IW.TICKS_PER_SECOND

    -- A firearm has more to check over than a kitchen knife, and someone who knows weapons
    -- checks faster. Maintenance is the skill the game already ties to looking after a
    -- weapon, so it is the one that pays here: a quarter off at level ten. This scaling
    -- belongs on the wind-up and not on the hold, because this is the half that is actually
    -- the character doing something.
    if self.weapon and self.weapon:isRanged() then
        duration = duration * 1.25
    end
    local maintenance = self.character:getPerkLevel(Perks.Maintenance) or 0
    duration = duration * (1 - 0.025 * maintenance)

    -- ISBaseTimedAction:adjustMaxTime multiplies this again for unhappiness, drink, wounded
    -- hands and body temperature, so the sandbox figure is the baseline for a healthy
    -- character rather than a promise.
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

    -- Walking is allowed. The engine blends an action anim over locomotion on its own, and
    -- this is the same clip ISEquipWeaponAction plays while walking. Running and raising
    -- the weapon still end it: both mean the player's attention has gone elsewhere.
    o.stopOnWalk = false
    o.stopOnRun = true
    o.stopOnAim = true

    o.maxTime = o:getDuration()
    return o
end
