-- Disposable Flycast profile only. Supported controller API plus read-only
-- guest telemetry; no guest memory writes or save-state loads.
local frame, title_seen, title_frame = 0, false, 0
local out = assert(io.open('font-selector-probe.csv', 'w'))
out:write('frame,vm,mode,selector,held,pressed,surfaces,nonnative\n')
flycast_callbacks = {vblank = function()
    frame = frame + 1
    local m = flycast.memory
    local pc = m.read32(0x8c1dbe24)
    if not title_seen and pc >= 0x8c01923c and pc < 0x8c019420 then
        title_seen, title_frame = true, frame
    end
    local f = io.open('buttons.txt', 'r')
    local buttons = f and tonumber(f:read('*a')) or 0
    if f then f:close() end
    -- Short Start pulses skip the logos/movie; stop pulsing on the title.
    if not title_seen and frame > 1200 and frame % 120 < 6 then buttons = 8 end
    if title_seen and frame >= title_frame+30 and frame < title_frame+36 then buttons = 8 end
    flycast.input.releaseButtons(1, 0xffff)
    if buttons and buttons ~= 0 then flycast.input.pressButtons(1, buttons) end
    if frame % 10 == 0 then
        local c = m.read32(0x8c169bac)
        local held, pressed, surfaces, nonnative = 0, 0, 0, 0
        if c >= 0x8c000000 and c < 0x8d000000 then
            held, pressed = m.read32(c+8), m.read32(c+16)
        end
        if m.read32(0x8c07b28e) == 0x2f962f86 then
            for i = 0, 47 do
                local ptr = m.read32(0x8c1f0cf8+i*92+0x44)
                if ptr >= 0x8c000000 and ptr < 0x8d000000 then
                    surfaces = surfaces+1
                    if m.read16(ptr+12) ~= 0 then nonnative = nonnative+1 end
                end
            end
        end
        out:write(string.format('%d,%08x,%d,%d,%08x,%08x,%d,%d\n', frame,pc,
            m.read8(0x8c07bbe0),m.read8(0x8c07bbe1),held,pressed,surfaces,nonnative))
        out:flush()
    end
    if frame == 36000 then out:close();flycast.emulator.exit() end
end}
