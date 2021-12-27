from opentrons import protocol_api

metadata = {
    'protocolName': 'RNA Normalization I & II',
    'author': 'Rami Farawi <rami.farawi@opentrons.com>',
    'source': 'Custom Protocol Request',
    'apiLevel': '2.11'
}


def run(ctx: protocol_api.ProtocolContext):

    [
     _num_col,
     _csv,
     _p20_mount,
     _m20_mount
    ] = get_values(  # noqa: F821 (<--- DO NOT REMOVE!)
        "_num_col",
        "_csv",
        "_p20_mount",
        "_m20_mount")

    # VARIABLES

    # number of columsn in tc plate
    num_col = int(_num_col)

    # should be formatted as so:
    # SlotSource | Source | SourceVolH20 | SourceVolRNA | SlotDest | Dest
    csv = _csv

    # change pipette mounts here to "left" or "right", respectively
    p20_mount = _p20_mount
    m20_mount = _m20_mount

    # MODULES
    thermocyc = ctx.load_module('thermocycler')

    # LABWARE
    tuberacks = [ctx.load_labware(
                 'opentrons_24_tuberack_eppendorf_1.5ml_safelock_snapcap',
                 slot, label='Sample Tuberack')
                 for slot in ['1', '2', '4', '5']]
    tc_plate = thermocyc.load_labware('nest_96_wellplate_100ul_pcr_full_skirt')
    water_plate = ctx.load_labware('abgene_96_wellplate_200ul', '3',
                                   label='Abgene Plate')

    # TIPRACKS
    tipracks = [ctx.load_labware('opentrons_96_filtertiprack_20ul', slot)
                for slot in ['6', '9']]

    # INSTRUMENTS
    p20 = ctx.load_instrument('p20_single_gen2', p20_mount, tip_racks=tipracks)
    m20 = ctx.load_instrument('p20_multi_gen2', m20_mount, tip_racks=tipracks)

    def pick_up(pip):
        try:
            pip.pick_up_tip()
        except protocol_api.labware.OutOfTipsError:
            ctx.pause("Replace tip racks on Slots 6 and 9")
            pip.reset_tipracks()
            pick_up()

    # MAPPING
    slot_source = 0
    source_well = 1
    transfer_vol_water = 2
    transfer_vol_rna = 3
    slot_dest = 4
    dest_well = 5

    all_rows = [[val.strip() for val in line.split(',')]
                for line in csv.splitlines()
                if line.split(',')[0].strip()][1:]

    print(tuberacks)

    # protocol
    ctx.comment('\n\nPRE-COOL THERMOCYC\n')
    if thermocyc.lid_position != 'open':
        thermocyc.open_lid()
    thermocyc.set_block_temperature(4)
    thermocyc.set_lid_temperature(105)

    ctx.comment('\n\nMOVING WATER TO PLATE\n')
    pick_up(p20)
    for water_well, the in zip(water_plate.wells(), all_rows):
        p20.aspirate(int(the[transfer_vol_water]), water_well)
        p20.dispense(int(the[transfer_vol_water]),
                     ctx.loaded_labwares[
                     int(the[slot_dest])
                     ].wells_by_name()[
                     the[dest_well]
                     ])
    p20.drop_tip()

    ctx.comment('\n\nMOVING RNA TO PLATE\n')
    for the in all_rows:
        pick_up(p20)
        p20.aspirate(int(the[transfer_vol_rna]),
                     ctx.loaded_labwares[
                     int(the[slot_source])
                     ].wells_by_name()[
                     the[source_well]
                     ])
        p20.dispense(int(the[transfer_vol_rna]),
                     ctx.loaded_labwares[
                     int(the[slot_dest])
                     ].wells_by_name()[
                     the[dest_well]
                     ])
        p20.blow_out(ctx.loaded_labwares[int(the[slot_dest])].wells_by_name()[
                    the[dest_well]].top(z=-5))
        p20.touch_tip()
        p20.drop_tip()

    ctx.pause('''
                 RNA and water on Thermocycler Plate.

                 Replace the 96 well plate containing water on Slot 3 with
                 the exact same 96 well plate with cold mastermix in Column 1.

                 Select "Resume" on the Opentron App to continue.

              ''')

    ctx.comment('\n\nMOVING MASTERMIX TO PLATE\n')
    mmx_plate = water_plate
    mmx = mmx_plate.rows()[0][0]
    for col in tc_plate.rows()[0][:num_col]:
        pick_up(m20)
        m20.aspirate(4, mmx)
        m20.dispense(4, col)
        m20.mix(4, 12, col, rate=0.5)
        m20.blow_out(ctx.loaded_labwares[int(the[slot_dest])].wells_by_name()[
                    the[dest_well]].top(z=-5))
        m20.touch_tip()
        m20.drop_tip()

    ctx.comment('\n\nRUN THERMOCYCLER PROFILE\n')

    profile = [
                {'temperature': 25, 'hold_time_seconds': 10},
                {'temperature': 50, 'hold_time_seconds': 10},
                {'temperature': 85, 'hold_time_seconds': 5}
                ]

    thermocyc.close_lid()
    thermocyc.execute_profile(steps=profile,
                              repetitions=1,
                              block_max_volume=20)
    thermocyc.open_lid()