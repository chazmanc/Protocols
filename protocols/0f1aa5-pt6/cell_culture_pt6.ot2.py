from opentrons import labware, instruments, robot
from otcustomizers import StringSelection

metadata = {
    'protocolName': 'Cell Culture Assay: Part 6',
    'author': 'Nick <protocols@opentrons.com>',
    'source': 'Custom Protocol Request'
}

# create custom labware
vial_rack_name = 'fisherbrand_24_vilerack'
if vial_rack_name not in labware.list():
    labware.create(
        vial_rack_name,
        grid=(6, 4),
        spacing=(18, 18),
        diameter=8,
        depth=40,
        volume=5000
    )

tiprack300_name = 'fisherbrand_96_tiprack_300ul'
if tiprack300_name not in labware.list():
    labware.create(
        tiprack300_name,
        grid=(12, 8),
        spacing=(9, 9),
        diameter=3,
        depth=60
    )

tiprack10_name = 'fisherbrand_96_tiprack_10ul'
if tiprack10_name not in labware.list():
    labware.create(
        tiprack10_name,
        grid=(12, 8),
        spacing=(9, 9),
        diameter=3,
        depth=60
    )

# load labware
plate_F = labware.load(
    'corning_96_wellplate_360ul_flat', '1', 'plate F')
micro_tuberack = labware.load(
    'opentrons_24_tuberack_eppendorf_1.5ml_safelock_snapcap',
    '4',
    'microfuge tubes'
)
res12 = labware.load('usascientific_12_reservoir_22ml', '5')
tips300m = [
    labware.load(tiprack300_name, slot) for slot in ['6', '7', '8', '9']]
tips300s = [
    labware.load(tiprack300_name, slot) for slot in ['10', '11']]

# reagents
ctg = res12.wells('A1')
pbs = res12.wells('A2', length=2)
media = res12.wells('A4')
mgs = res12.wells('A5')
hpr = res12.wells('A6')
waste = res12.wells('A12').top()

ns = micro_tuberack.wells('D1')
hps = micro_tuberack.wells('A2')


def run_custom_protocol(
        p300_multi_mount: StringSelection('right', 'left') = 'right',
        p300_single_mount: StringSelection('left', 'right') = 'left',
):

    # pipettes
    p300 = instruments.P300_Single(mount=p300_single_mount, tip_racks=tips300s)
    m300 = instruments.P300_Multi(mount=p300_multi_mount, tip_racks=tips300m)

    tip300s_count = 0
    tip300m_count = 0
    tip300s_max = len(tips300s)*96
    tip300m_max = len(tips300m)*12

    def pick_up(pip):
        nonlocal tip300s_count
        nonlocal tip300m_count

        if pip == p300:
            if tip300s_count == tip300s_max:
                robot.pause('Refill P300 single tip racks before resuming.')
                tip300m_count = 0
                p300.reset()
            tip300s_count += 1
        else:
            if tip300m_count == tip300m_max:
                robot.pause('Refill P300 multi tip racks before resuming.')
                tip300m_count = 0
                m300.reset()
            tip300m_count += 1
        pip.pick_up_tip()

    # distribute HPS
    pick_up(p300)
    p300.transfer(200, hps, [well.top() for well in plate_F.rows('A')[:2]])
    p300.drop_tip()

    # serial dilution
    dil_sources = [
        col[:6] for col in plate_F.columns()[:2]]
    dil_dests = [
        col[1:7] for col in plate_F.columns()[:2]]
    # distribute media
    pick_up(p300)
    p300.distribute(
        100,
        media,
        [d.top() for set in dil_dests for d in set],
        new_tip='never'
    )
    # serial dilution
    for s_set, d_set in zip(dil_sources, dil_dests):
        if not p300.tip_attached:
            pick_up(p300)
        for s, d in zip(s_set, d_set):
            p300.transfer(100, s, d, new_tip='never')
            p300.mix(3, 100, d)
            p300.blow_out()
        p300.drop_tip()

    # remove waste from last row
    for well in plate_F.rows('G')[:2]:
        pick_up(p300)
        p300.transfer(100, well, waste, new_tip='never')
        p300.drop_tip()

    # distribute HPR
    pick_up(m300)
    m300.distribute(
        50, hpr, [well.top() for well in plate_F.rows('A')], new_tip='never')
    m300.drop_tip()
