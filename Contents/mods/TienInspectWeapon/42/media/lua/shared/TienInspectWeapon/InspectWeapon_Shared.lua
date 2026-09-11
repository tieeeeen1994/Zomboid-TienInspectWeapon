--[[
    Tien's Weapon Inspection - shared core.

    Everything the mod knows about a weapon is read here, in one pass, into a plain list
    of rows that the window then draws. Nothing in this file touches the UI or the
    network, so the same reading can be asked for from anywhere.

    Build 42 splits a melee weapon's wear three ways and the split is not obvious from
    the item tooltip, which is most of the reason this mod exists:

      getCondition()      the haft. On an axe this is the handle, and it is what breaks
                          when you swing into a wall. Vanilla labels it "Handle Condition"
                          precisely when the item also has a head, and plain "Condition"
                          otherwise, so this file does the same.
      getHeadCondition()  the business end, present only on items whose script sets
                          HeadCondition (axes, hammers, crafted spears). Guarded by
                          hasHeadCondition(), because most weapons have none and the
                          getter returns a meaningless 0 for them.
      getSharpness()      an edge's keenness, 0..getMaxSharpness(), on anything with
                          Sharpness in its script. Falls on its own with use and is put
                          back with a whetstone. Guarded by hasSharpness().

    Firearms have none of those three beyond the first, so they get their own rows.
]]

TienInspectWeapon = TienInspectWeapon or {}
local IW = TienInspectWeapon

-- Keep in step with modversion in mod.info.
IW.VERSION = "1.0.0"

-- The name of both the keybinding and the animation node in
-- media/AnimSets/player/actions/TienInspectWeapon.xml. The two are unrelated to each
-- other but a mod that renames one and forgets the other is a mod with no animation,
-- so they are spelled once, here.
IW.ACTION_ANIM = "TienInspectWeapon"
IW.KEYBIND = "TienInspectWeapon"

IW.DEBUG = false

function IW.debug(fmt, ...)
    if IW.DEBUG then
        print("TienInspectWeapon: " .. string.format(fmt, ...))
    end
end

function IW.opt(name, default)
    local vars = SandboxVars and SandboxVars.TienInspectWeapon
    if not vars then return default end
    local v = vars[name]
    if v == nil then return default end
    return v
end

--[[ What counts as inspectable ]]

-- Bare hands are a HandWeapon too - the game hands out Base.BareHands so that punching
-- has damage numbers to work from - and inspecting your own fist is not the feature.
function IW.isInspectable(item)
    if not item then return false end
    if not instanceof(item, "HandWeapon") then return false end
    if item:getFullType() == "Base.BareHands" then return false end
    return true
end

-- The primary hand first, then the secondary, so that a torch in one hand and a machete
-- in the other still inspects the machete, and a two-handed weapon - which the game puts
-- in both hands - is found either way.
function IW.findWeapon(player)
    if not player then return nil end
    local primary = player:getPrimaryHandItem()
    if IW.isInspectable(primary) then return primary end
    local secondary = player:getSecondaryHandItem()
    if IW.isInspectable(secondary) then return secondary end
    return nil
end

--[[ Reading the numbers ]]

local function safeRatio(value, max)
    if not value or not max or max <= 0 then return nil end
    local r = value / max
    if r < 0 then return 0 end
    if r > 1 then return 1 end
    return r
end

-- pcall around every getter that only some items answer. hasSharpness() and
-- hasHeadCondition() already gate the two that matter, but this mod is read by whatever
-- weapon a modded server happens to hand the player, and a missing method on one line
-- should cost that line and not the window.
local function ask(item, method, ...)
    if not item or not item[method] then return nil end
    local ok, value = pcall(item[method], item, ...)
    if not ok then return nil end
    return value
end

-- The same colour the game's own weapon tooltip gives these bars. HandWeapon.DoTooltip
-- interpolates from the player's "bad" highlight colour to their "good" one across the
-- fraction, and reading those two out of Core rather than hard-coding red and green is
-- what makes the window follow a player who has changed them - which anyone playing with
-- the colourblind-friendly pair has.
function IW.colorFor(ratio)
    local core = getCore()
    if ratio == nil or not core then return 0.62, 0.62, 0.62 end

    local bad, good = core:getBadHighlitedColor(), core:getGoodHighlitedColor()
    if not bad or not good then return 0.62, 0.62, 0.62 end

    return bad:getR() + (good:getR() - bad:getR()) * ratio,
           bad:getG() + (good:getG() - bad:getG()) * ratio,
           bad:getB() + (good:getB() - bad:getB()) * ratio
end

--[[
    A bar row: a label and a coloured bar, and nothing else.

    This is exactly what the game does. Every one of these reaches the tooltip as
    setLabel() followed by setProgress(fraction, r, g, b, alpha) with no setValue beside
    it, so the game never puts a figure on a weapon's wear anywhere the player can see
    one. Printing "11 / 13" here would be this mod quietly telling them something the
    rest of the game does not.
]]
local function bar(rows, key, label, value, max)
    local ratio = safeRatio(value, max)
    if ratio == nil then return end

    table.insert(rows, { kind = "bar", key = key, label = label, ratio = ratio })
end

local function line(rows, key, label, text, warn)
    if text == nil or text == "" then return end
    table.insert(rows, { kind = "line", key = key, label = label, text = tostring(text), warn = warn })
end

-- A standalone sentence with no value beside it, which is how the game states a weapon's
-- faults: "Weapon jammed. Rack it." is the whole row. warn is false for the ones that are
-- merely informational, so the amber is kept for the things that are actually wrong.
local function note(rows, text, warn)
    if text == nil or text == "" then return end
    table.insert(rows, { kind = "note", text = tostring(text), warn = warn ~= false })
end

-- Rows for a firearm: what is in it and whether it will fire.
--
-- Every label and every sentence here is the game's own. Reusing its keys rather than
-- writing new ones means the wording a player already knows from the tooltip is the
-- wording they get here, in whatever language they play in, and this mod ships no
-- translation of its own to go stale.
local function firearmRows(rows, weapon)
    -- InventoryItem.DoTooltipEmbedded prints this as "current/max" text, not a bar:
    -- rounds are counted, not worn.
    local maxAmmo = ask(weapon, "getMaxAmmo")
    local ammo = ask(weapon, "getCurrentAmmoCount")
    if ammo and maxAmmo and maxAmmo > 0 then
        line(rows, "ammo", getText("Tooltip_weapon_AmmoCount"),
            string.format("%d/%d", ammo, maxAmmo), ammo <= 0)
    elseif ammo then
        line(rows, "ammo", getText("Tooltip_weapon_AmmoCount"), tostring(ammo), ammo <= 0)
    end

    -- getAmmoType() hands back an AmmoType object, not a string; getItemKey() is the
    -- full type of the round, which the script manager turns into its display name.
    local ammoType = ask(weapon, "getAmmoType")
    local ammoKey
    if ammoType then
        local ok, key = pcall(function() return ammoType:getItemKey() end)
        if ok then ammoKey = key end
    end
    if ammoKey and ammoKey ~= "" then
        local script = getScriptManager():getItem(ammoKey)
        line(rows, "ammoType", getText("ContextMenu_AmmoType"),
            script and script:getDisplayName() or ammoKey)
    end

    if ask(weapon, "isJammed") == true then
        note(rows, getText("Tooltip_weapon_Jammed"))
    end

    if ask(weapon, "haveChamber") == true then
        if ask(weapon, "isSpentRoundChambered") == true then
            note(rows, getText("Tooltip_weapon_SpentRoundChambered"))
        elseif ask(weapon, "isRoundChambered") ~= true then
            note(rows, getText("Tooltip_weapon_NoRoundChambered"))
        end
    end

    local spent = ask(weapon, "getSpentRoundCount")
    if spent and spent > 0 then
        line(rows, "spentRounds", getText("Tooltip_weapon_SpentRounds"), tostring(spent), true)
    end

    -- Only guns that take one have anything to say about a magazine.
    local magType = ask(weapon, "getMagazineType")
    if magType and magType ~= "" then
        if ask(weapon, "isContainsClip") == true then
            note(rows, getText("Tooltip_weapon_ContainsClip"), false)
        else
            note(rows, getText("Tooltip_weapon_NoClip"))
        end
    end
end

--[[
    The reading itself.

    Returns the rows the window draws, in the order the game's own tooltip lists them.
    This window is deliberately the tooltip's twin: the mod's worth is that it arrives
    on a keypress and stays put, not that it presents the numbers differently.
]]
function IW.inspect(weapon)
    local rows = {}
    if not weapon then return rows end

    local hasHead = ask(weapon, "hasHeadCondition") == true

    -- Vanilla names this one for the part it actually is, and only when there is a head
    -- to tell it apart from. Doing the same avoids teaching the player something the
    -- rest of the game will contradict.
    local conditionLabel = hasHead
        and getText("Tooltip_weapon_HandleCondition")
        or getText("Tooltip_weapon_Condition")

    local condition, conditionMax = ask(weapon, "getCondition"), ask(weapon, "getConditionMax")
    bar(rows, "condition", conditionLabel, condition, conditionMax)

    if hasHead then
        local head, headMax = ask(weapon, "getHeadCondition"), ask(weapon, "getHeadConditionMax")
        bar(rows, "head", getText("Tooltip_weapon_HeadCondition"), head, headMax)
    end

    if ask(weapon, "hasSharpness") == true then
        local sharp, sharpMax = ask(weapon, "getSharpness"), ask(weapon, "getMaxSharpness")
        -- Vanilla feeds getSharpness() straight to setProgress, treating it as already
        -- being a 0..1 fraction, which it is for every item in the game: the scripts set
        -- Sharpness = 1.0 for a new edge. Dividing by the maximum is the same bar for all
        -- of those and a correct one for a modded weapon that picked a different scale.
        if not sharpMax or sharpMax <= 0 then sharpMax = 1.0 end
        bar(rows, "sharpness", getText("Tooltip_weapon_Sharpness"), sharp, sharpMax)
    end

    if ask(weapon, "isRanged") == true then
        firearmRows(rows, weapon)
    end

    -- Repairs are worth showing because each one makes the next less effective -
    -- FixingManager.getCondRepaired and getChanceOfFail both divide by the count - and
    -- nothing else on screen says so.
    --
    -- The counter starts at zero and fixItem does setHaveBeenRepaired(get + 1), so the
    -- number it holds is the number of repairs, with nothing to subtract.
    -- getTimesRepaired() is the same field under a Build 42 name.
    local repaired = ask(weapon, "getTimesRepaired") or ask(weapon, "getHaveBeenRepaired")
    if repaired and repaired > 0 then
        line(rows, "repairs",
            hasHead and getText("Tooltip_handle_Repaired") or getText("Tooltip_weapon_Repaired"),
            tostring(repaired))
    end

    -- hasTimesHeadRepaired() is not optional politeness: getTimesHeadRepaired() falls
    -- back to the handle's counter when an item carries no head-repair attribute, so
    -- asking without checking reports the handle's repairs twice under two labels.
    if ask(weapon, "hasTimesHeadRepaired") == true then
        local headRepairs = ask(weapon, "getTimesHeadRepaired")
        if headRepairs and headRepairs > 0 then
            line(rows, "headRepairs", getText("Tooltip_head_Repaired"), tostring(headRepairs))
        end
    end

    -- The game's damage bar is (min + max) / 5, which is the average over 2.5 - there is
    -- no per-weapon maximum to measure against, so it scales every weapon on one fixed
    -- ruler and lets the best of them fill the bar. Copied rather than reinvented, for
    -- the same reason as everything else here: a player who has learned what a half-full
    -- damage bar means from the tooltip reads this one the same way.
    local minDamage, maxDamage = ask(weapon, "getMinDamage"), ask(weapon, "getMaxDamage")
    if minDamage and maxDamage and maxDamage > 0 then
        bar(rows, "damage", getText("Tooltip_weapon_Damage"), minDamage + maxDamage, 5.0)
    end

    if #rows == 0 then
        note(rows, getText("IGUI_TienInspectWeapon_NothingToReport"))
    end

    return rows
end
