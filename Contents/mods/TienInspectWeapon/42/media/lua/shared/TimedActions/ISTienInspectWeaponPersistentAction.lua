--[[
    Tien's Weapon Inspection - the Persistent mode action.

    With the InspectMode sandbox option on Persistent, an inspection is this one action and
    nothing else. The character raises the weapon and studies it in the hold's pose
    (TienInspectWeaponHold) for the raise time, on a real countdown with a progress circle,
    and when it finishes the window opens and the action is over. There is no hold behind
    it, so the window has no action to share a lifetime with: running, raising the weapon
    and starting other work leave it alone. Its close button, the inspect key, and the
    weapon leaving the character's hands put it away.

    It is the wind-up with two things changed, so it derives from ISTienInspectWeaponAction
    and keeps its isValid, update, getDuration and complete: the same light and held-weapon
    checks, the same InspectSeconds with the firearm and Maintenance scaling, the same
    server completion hook. What differs is the clip start() plays and what perform() does
    at the end - open the window rather than queue the hold.

    Everything said about multiplayer on ISTienInspectWeaponAction holds here. The server
    rebuilds this action from its Type by calling ISTienInspectWeaponPersistentAction:new,
    which is why it lives in media/lua/shared and has a new() of its own, and the window is
    opened from perform() because a multiplayer client never runs complete().
]]

require "TimedActions/ISTienInspectWeaponAction"
require "TienInspectWeapon/InspectWeapon_Shared"

local IW = TienInspectWeapon

ISTienInspectWeaponPersistentAction = ISTienInspectWeaponAction:derive("ISTienInspectWeaponPersistentAction")

function ISTienInspectWeaponPersistentAction:start()
    if isClient() then
        local current = self.character:getInventory():getItemById(self.weapon:getID())
        if current then self.weapon = current end
    end

    -- The hold's clip, not the wind-up's. This mode has no hold to settle into afterwards,
    -- so the studying pose is the whole of the look. It is a looped idle, so a raise time
    -- set longer than the clip keeps playing rather than freezing on its last frame.
    self:setActionAnim(IW.HOLD_ANIM)
end

-- The window opens here and belongs to nobody afterwards: it is not handed a back-reference
-- to this action, so closing it stops nothing, and this action ending closes nothing.
-- ISBaseTimedAction.perform is called directly, skipping ISTienInspectWeaponAction.perform,
-- which is the one that would queue the hold.
function ISTienInspectWeaponPersistentAction:perform()
    if self.character:isLocalPlayer() and ISTienInspectWeaponWindow then
        ISTienInspectWeaponWindow.open(self.character, self.weapon, IW.MODE_PERSISTENT)
    end
    ISBaseTimedAction.perform(self)
end

-- Spelled out rather than inherited so that the parameter names the network packet is
-- built from are this class's own, whatever the metatable lookup does.
function ISTienInspectWeaponPersistentAction:new(character, weapon)
    return ISTienInspectWeaponAction.new(self, character, weapon)
end
