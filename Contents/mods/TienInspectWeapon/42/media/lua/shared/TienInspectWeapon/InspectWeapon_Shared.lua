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
IW.VERSION = "1.0.5"

-- Every one of these names a node in media/AnimSets/player/actions, except KEYBIND, which
-- names the control binding and happens to share a spelling. A mod that renames a node and
-- forgets its Lua is a mod with no animation, so they are spelled once, here.
--
-- An inspection is two animations. ACTION_ANIM is the wind-up, played while the character
-- brings the weapon up and turns it over; HOLD_ANIM is the pose they settle into once the
-- window is open, and it is the one that has to survive being held for the whole ceiling.
IW.ACTION_ANIM = "TienInspectWeapon"
IW.HOLD_ANIM = "TienInspectWeaponHold"
IW.KEYBIND = "TienInspectWeapon"

--[[
    Timed action units per real second, at normal game speed.

    A timed action's maxTime is not seconds and not frames. BaseAction.update does
    `currentTime += GameTime.getMultiplier()` each tick and finishes when currentTime
    reaches maxTime, and GameTime's own conversion pair gives what that multiplier is
    worth:

        getMultiplierFromTimeDelta(dt) = dt * 0.8 * multiplierBias * 60
        getTimeDeltaFromMultiplier(m)  = m / 0.8 / multiplierBias / 60

    multiplierBias is 1.0 out of GameTime's constructor and nothing in the game's Lua
    touches it, so a second of real time is worth dt * 0.8 * 60 = 48 units, frame rate
    independent. That is the whole of the conversion, and it is here so that the sandbox
    option can be set in seconds like a person would expect.
]]
IW.TICKS_PER_SECOND = 48

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

local function clamp01(v)
    if v < 0 then return 0 end
    if v > 1 then return 1 end
    return v
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
-- runs ColorInfo.interp from the player's "bad" highlight colour to their "good" one
-- across the fraction, and reading those two out of Core rather than hard-coding red and
-- green is what makes the window follow a player who has changed them - which anyone
-- playing with the colourblind-friendly pair has.
--
-- The fraction is the unclamped one, as in vanilla: a damage bar past full keeps
-- extrapolating towards "good", and only the channels are held to 0..1, which is where
-- the renderer would have held them anyway. inverted swaps the ends, for the one bar -
-- blood - where more is worse.
function IW.colorFor(fraction, inverted)
    local core = getCore()
    if fraction == nil or not core then return 0.62, 0.62, 0.62 end

    local from, to = core:getBadHighlitedColor(), core:getGoodHighlitedColor()
    if not from or not to then return 0.62, 0.62, 0.62 end
    if inverted then from, to = to, from end

    return clamp01(from:getR() + (to:getR() - from:getR()) * fraction),
           clamp01(from:getG() + (to:getG() - from:getG()) * fraction),
           clamp01(from:getB() + (to:getB() - from:getB()) * fraction)
end

--[[
    A bar row: a label, a coloured bar, and the numbers behind it.

    The bar is exactly the game's: HandWeapon.DoTooltip's setProgress fraction and colour.
    The numbers are this mod's addition - vanilla draws the bar alone - because a bar
    cannot tell a weapon one repair from breaking apart from one that has a few left in
    it, and "2 / 13" can.

    fraction is kept as the game computed it, for the colour; ratio is the same number
    held to 0..1, which is what ObjectTooltip.DrawProgressBar fills the bar with. text is
    what is printed beside it, parentheses included.
]]
local function bar(rows, key, label, fraction, text, inverted)
    -- fraction ~= fraction is NaN, which a zero maximum produces.
    if fraction == nil or fraction ~= fraction then return end

    table.insert(rows, {
        kind = "bar", key = key, label = label, text = text,
        fraction = fraction, ratio = clamp01(fraction), inverted = inverted,
    })
end

local function ratioOf(value, max)
    if not value or not max or max <= 0 then return nil end
    return value / max
end

-- A number as briefly as it can be written without lying: two decimals at most, and none
-- of the trailing zeros, so condition reads "11" and sharpness "0.62" rather than
-- "11.00" and "0.620000".
local function num(v)
    if not v then return "?" end
    local s = string.format("%.2f", v)
    s = string.gsub(s, "0+$", "")
    s = string.gsub(s, "%.$", "")
    return s
end

local function outOf(value, max)
    return "(" .. num(value) .. " / " .. num(max) .. ")"
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
local function displayNameOf(fullType)
    if not fullType or fullType == "" then return nil end
    local script = getScriptManager():FindItem(fullType)
    return script and script:getDisplayName() or nil
end

-- The full type of the round the gun is set to fire. getAmmoType() hands back an AmmoType
-- object, not a string; getItemKey() is the full type.
local function currentRoundType(weapon)
    local ammoType = ask(weapon, "getAmmoType")
    if not ammoType then return nil end
    local ok, key = pcall(function() return ammoType:getItemKey() end)
    return ok and key or nil
end

-- What HandWeapon.DoTooltip labels the ammo row with: the magazine's name on a gun that
-- takes one, and the round's name on a gun that does not. There is no "Ammo Count" label
-- on a weapon's tooltip; that key is only used for items that are not weapons.
local function roundName(weapon, magType)
    if magType and magType ~= "" then
        return displayNameOf(magType)
    end
    return displayNameOf(currentRoundType(weapon))
end

--[[
    Gunworks Gang: which rounds are actually in the gun.

    Gunworks lets one gun take more than one kind of round - ball and armour-piercing fed
    out of the same magazine - but the game only knows one ammo type per gun, so Gunworks
    keeps its own record in the weapon's ModData as AmmoList: an array of round full
    types used as a stack. Rounds are appended as they are loaded and the last entry is
    the next to fire, so while a round is chambered that last entry is the one in the
    chamber and everything below it is what the magazine - or tube, or cylinder - still
    holds, top first reading downwards. Hot Brass and Tien's Magazine Bag read it the same
    way.

    The list is Gunworks' bookkeeping and the game's counts stay the authority:
    getCurrentAmmoCount() is the rounds outside the chamber and isRoundChambered() the one
    in it. Where they disagree - rounds loaded before Gunworks was added, or by a path it
    does not hook - the count wins, and rounds the list has no record of are put down as
    the gun's current ammo type, which is what Gunworks hands back when it unloads them.

    That includes a gun with no list at all, which is the usual state of one on a server:
    nothing writes AmmoList when loot spawns, so a gun or magazine found loaded has no
    record until its owner loads a round by hand. Treating that as "not a Gunworks gun"
    left such a gun with no rows, however full it was.

    Only read with SWMG active: AmmoList is a generic enough name for another mod to use.
]]
local gunworksLoaded = nil

local function gunworksActive()
    if gunworksLoaded == nil then
        local mods = getActivatedMods and getActivatedMods()
        gunworksLoaded = mods ~= nil and mods:contains("SWMG") == true
    end
    return gunworksLoaded
end

-- The rounds Gunworks has on record for this gun, or an empty list when it has none.
local function gunworksAmmoList(weapon)
    if ask(weapon, "hasModData") ~= true then return {} end

    local list = weapon:getModData().AmmoList
    if type(list) ~= "table" then return {} end
    return list
end

local function roundLabel(fullType)
    return displayNameOf(fullType) or fullType or "?"
end

local function gunworksRows(rows, weapon, list)
    local top = #list

    if ask(weapon, "isRoundChambered") == true then
        line(rows, "chamber", getText("IGUI_TienInspectWeapon_Chamber"),
            roundLabel(list[top] or currentRoundType(weapon)))
        top = math.max(top - 1, 0)
    end

    local count = ask(weapon, "getCurrentAmmoCount") or 0
    if count <= 0 then return end

    -- Tallied top down, so the first type listed is the next one to feed.
    local order, tally = {}, {}
    local function add(fullType, n)
        local key = fullType or ""
        if not tally[key] then
            tally[key] = 0
            table.insert(order, key)
        end
        tally[key] = tally[key] + n
    end

    local recorded = math.min(count, top)
    for i = top, top - recorded + 1, -1 do
        add(list[i], 1)
    end
    if count > recorded then
        add(currentRoundType(weapon), count - recorded)
    end

    local magType = ask(weapon, "getMagazineType")
    local label = (magType and magType ~= "")
        and getText("IGUI_TienInspectWeapon_InMagazine")
        or getText("IGUI_TienInspectWeapon_Loaded")

    -- One row per round type, the label on the first only, so a mixed load reads as a
    -- short list under one heading.
    for i, key in ipairs(order) do
        line(rows, "loaded" .. i, i == 1 and label or "",
            string.format("%dx %s", tally[key], roundLabel(key ~= "" and key or nil)))
    end
end

--[[
    Gunworks Gang: which magazine is actually in the gun.

    Gunworks lets one gun take more than one magazine - a 30-round STANAG or a 150-round
    drum in the same rifle - and on insert sets the gun's magazine type and capacity to
    whichever went in. In multiplayer that happens on the server, and
    syncHandWeaponFields, which is how the server tells the owner about the gun, carries
    the round count, the weapon parts and the ModData but not getMagazineType() or
    getMaxAmmo(). The owner's copy keeps the previous magazine's name and capacity -
    "30Rds ... 150+1 / 30" - until Gunworks restores them on the next equip or game
    start. The game's own tooltip shows the same stale pair, and no gun pack can fix it.

    Gunworks' record of the magazine, ModData.MagazineType, does arrive with the ModData,
    and it is what Gunworks itself restores the gun from. So with SWMG active and a
    magazine in, that is the magazine this names and takes the capacity from.
    Single-player is unaffected: there the two already agree.
]]
local capacityOf = {}

-- A magazine's capacity is only on an instance - the item script has no getter for it -
-- so one is made per type, as Gunworks' own restore does, and remembered: this runs every
-- frame the window is open.
local function magazineCapacity(magType)
    if capacityOf[magType] == nil then
        local mag = instanceItem and instanceItem(magType)
        capacityOf[magType] = mag and ask(mag, "getMaxAmmo") or false
    end
    return capacityOf[magType] or nil
end

local function loadedMagazine(weapon)
    local magType, maxAmmo = ask(weapon, "getMagazineType"), ask(weapon, "getMaxAmmo")

    if gunworksActive() and ask(weapon, "isContainsClip") == true
            and ask(weapon, "hasModData") == true then
        local recorded = weapon:getModData().MagazineType
        if type(recorded) == "string" and recorded ~= "" and recorded ~= magType then
            magType, maxAmmo = recorded, magazineCapacity(recorded) or maxAmmo
        end
    end

    return magType, maxAmmo
end

local function firearmRows(rows, weapon)
    local magType, maxAmmo = loadedMagazine(weapon)

    -- "12+1 / 15": the rounds in the gun, a +1 for one in the chamber, and the capacity.
    -- Text, not a bar: rounds are counted, not worn. Vanilla shows nothing at all for a
    -- weapon with no capacity, and does not colour an empty gun.
    if maxAmmo and maxAmmo > 0 then
        local count = string.format("%d", ask(weapon, "getCurrentAmmoCount") or 0)
        if ask(weapon, "isRoundChambered") == true then
            count = count .. "+1"
        end
        line(rows, "ammo", roundName(weapon, magType) or getText("Tooltip_weapon_AmmoCount"),
            string.format("%s / %d", count, maxAmmo))
    end

    if gunworksActive() then
        gunworksRows(rows, weapon, gunworksAmmoList(weapon))
    end

    -- These three are one if/elseif chain in vanilla, so at most one of them shows: a
    -- jammed gun says only that it is jammed, and the chamber warning is only given when
    -- there are rounds in the gun that could have been chambered.
    if ask(weapon, "isJammed") == true then
        note(rows, getText("Tooltip_weapon_Jammed"))
    elseif ask(weapon, "haveChamber") == true
            and ask(weapon, "isRoundChambered") ~= true
            and (ask(weapon, "getCurrentAmmoCount") or 0) > 0 then
        if ask(weapon, "isSpentRoundChambered") == true then
            note(rows, getText("Tooltip_weapon_SpentRoundChambered"))
        else
            note(rows, getText("Tooltip_weapon_NoRoundChambered"))
        end
    else
        local spent = ask(weapon, "getSpentRoundCount")
        if spent and spent > 0 then
            line(rows, "spentRounds", getText("Tooltip_weapon_SpentRounds"),
                string.format("%d / %d", spent, maxAmmo or 0), true)
        end
    end

    -- Only guns that take one have anything to say about a magazine. Vanilla prints both
    -- sentences in the same plain colour, so neither is a warning here.
    if magType and magType ~= "" then
        if ask(weapon, "isContainsClip") == true then
            note(rows, getText("Tooltip_weapon_ContainsClip"), false)
        else
            note(rows, getText("Tooltip_weapon_NoClip"), false)
        end
    end
end

--[[
    The reading itself.

    Returns the rows the window draws, in the order HandWeapon.DoTooltip lists them, with
    the repair counts after, where InventoryItem.DoTooltipEmbedded adds them. This window
    is deliberately the tooltip's twin: the mod's worth is that it arrives on a keypress
    and stays put, not that it presents the numbers differently.

    character is whoever is holding the weapon, which the range bar is worked out for.
]]
function IW.inspect(weapon, character)
    local rows = {}
    if not weapon then return rows end

    local hasHead = ask(weapon, "hasHeadCondition") == true

    -- Sharpness comes first, and goes to the bar exactly as getSharpness() returns it.
    --
    -- It is tempting to divide by getMaxSharpness(), and wrong: that is not a scale. It
    -- is getHeadCondition() / getHeadConditionMax() - or the handle's fraction on an item
    -- with no head - and getSharpness() is capped at it, so a worn blade is also a blunt
    -- one. Dividing one by the other shows a half-worn, half-sharp knife as fully sharp.
    --
    -- The number shown is out of 1, the scale the bar is drawn against, not out of
    -- getMaxSharpness(): that would put the head's wear in the sharpness row.
    if ask(weapon, "hasSharpness") == true then
        local sharpness = ask(weapon, "getSharpness")
        bar(rows, "sharpness", getText("Tooltip_weapon_Sharpness"), sharpness,
            outOf(sharpness, 1))
    end

    -- Vanilla names this one for the part it actually is, and only when there is a head
    -- to tell it apart from. Doing the same avoids teaching the player something the
    -- rest of the game will contradict.
    local conditionLabel = hasHead
        and getText("Tooltip_weapon_HandleCondition")
        or getText("Tooltip_weapon_Condition")

    local condition, conditionMax = ask(weapon, "getCondition"), ask(weapon, "getConditionMax")
    bar(rows, "condition", conditionLabel, ratioOf(condition, conditionMax),
        outOf(condition, conditionMax))

    if hasHead then
        local head, headMax = ask(weapon, "getHeadCondition"), ask(weapon, "getHeadConditionMax")
        bar(rows, "head", getText("Tooltip_weapon_HeadCondition"), ratioOf(head, headMax),
            outOf(head, headMax))
    end

    -- The game's damage bar is (min + max) / 5, which is the average over 2.5 - there is
    -- no per-weapon maximum to measure against, so it scales every weapon on one fixed
    -- ruler and lets the best of them fill the bar. Copied rather than reinvented, for
    -- the same reason as everything else here: a player who has learned what a half-full
    -- damage bar means from the tooltip reads this one the same way.
    --
    -- With no maximum, "x / y" would be a made-up figure, so the numbers beside this one
    -- are the weapon's damage range instead.
    local minDamage, maxDamage = ask(weapon, "getMinDamage"), ask(weapon, "getMaxDamage")
    if minDamage and maxDamage and maxDamage > 0 then
        bar(rows, "damage", getText("Tooltip_weapon_Damage"), (minDamage + maxDamage) / 5.0,
            "(" .. num(minDamage) .. " - " .. num(maxDamage) .. ")")
    end

    -- Blood is the one bar where full is bad, so vanilla runs its colour from good to bad
    -- instead, and shows it only once there is some.
    local blood = ask(weapon, "getBloodLevel")
    if blood and blood ~= 0 then
        bar(rows, "blood", getText("Tooltip_clothing_bloody"), blood, outOf(blood, 1), true)
    end

    if ask(weapon, "isRanged") == true then
        -- Range against a fixed 40 tiles, and for the character holding it: Aiming skill
        -- is part of getMaxRange. Vanilla asks on behalf of IsoPlayer.getInstance(), which
        -- is the same person everywhere but split-screen.
        local range = character and ask(weapon, "getMaxRange", character)
        if range then
            bar(rows, "range", getText("Tooltip_weapon_Range"), range / 40.0, outOf(range, 40))
        end

        firearmRows(rows, weapon)
    end

    -- Repairs are worth showing because each one makes the next less effective -
    -- FixingManager.getCondRepaired and getChanceOfFail both divide by the count - and
    -- nothing else on screen says so.
    --
    -- The counter starts at zero and fixItem does setHaveBeenRepaired(get + 1), so the
    -- number it holds is the number of repairs, with nothing to subtract.
    -- getTimesRepaired() is the same field under a Build 42 name. Vanilla writes it as
    -- "3x".
    --
    -- The label turns into "Handle Repaired" when the item keeps a separate head-repair
    -- count - hasTimesHeadRepaired(), not hasHeadCondition(). The two usually agree, but
    -- it is the counter's existence the tooltip goes by.
    local hasHeadRepairs = ask(weapon, "hasTimesHeadRepaired") == true
    local repaired = ask(weapon, "getHaveBeenRepaired") or ask(weapon, "getTimesRepaired")
    if repaired and repaired > 0 then
        line(rows, "repairs",
            hasHeadRepairs and getText("Tooltip_handle_Repaired") or getText("Tooltip_weapon_Repaired"),
            string.format("%dx", repaired))
    end

    -- hasTimesHeadRepaired() is not optional politeness: getTimesHeadRepaired() falls
    -- back to the handle's counter when an item carries no head-repair attribute, so
    -- asking without checking reports the handle's repairs twice under two labels.
    if hasHeadRepairs then
        local headRepairs = ask(weapon, "getTimesHeadRepaired")
        if headRepairs and headRepairs > 0 then
            line(rows, "headRepairs", getText("Tooltip_head_Repaired"),
                string.format("%dx", headRepairs))
        end
    end

    if #rows == 0 then
        note(rows, getText("IGUI_TienInspectWeapon_NothingToReport"))
    end

    return rows
end
