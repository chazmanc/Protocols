import math

metadata = {
    'protocolName': 'Nextera DNA Flex NGS Library Prep: Tagment DNA',
    'author': 'Nick <protocols@opentrons.com>',
    'source': 'Custom Protocol Request',
    'apiLevel': '2.0'
}


def run(ctx):

    [number_of_samples_to_process, p50_single_mount, using_p50_multi,
        p50_multi_mount_if_applicable] = get_values(  # noqa: F821
        'number_of_samples_to_process', 'p50_single_mount', 'using_p50_multi',
        'p50_multi_mount_if_applicable')

    # check:
    if (
        using_p50_multi == 'yes'
        and p50_single_mount == p50_multi_mount_if_applicable
    ):
        raise Exception('Input different mounts for P50 and P300 multi-channel \
pipettes')
    if number_of_samples_to_process > 96 or number_of_samples_to_process < 1:
        raise Exception('Invalid number of samples to process (must be between \
1 and 96).')

    # load labware and modules
    rxn_plate = ctx.load_labware(
        'biorad_96_wellplate_200ul_pcr', '1', 'tagmentation reaction plate')
    tuberack = ctx.load_labware(
        'opentrons_24_aluminumblock_nest_1.5ml_snapcap',
        '2',
        'reagent tuberack'
    )

    # reagents
    mm = tuberack.columns()[0][:2]
    blt = [well.top(-19) for well in tuberack.columns()[1]]
    tb1 = [well.top(-19) for well in tuberack.columns()[2]]

    samples = rxn_plate.wells()[:number_of_samples_to_process]

    # pipettes
    slots = ['4', '5'] if number_of_samples_to_process > 94 else ['4']
    tips50s = [
        ctx.load_labware('opentrons_96_tiprack_300ul', slot) for slot in slots]
    p50 = ctx.load_instrument(
        'p50_single', mount=p50_single_mount, tip_racks=tips50s)

    # create mastermix
    num_transfers_each = math.ceil(11*number_of_samples_to_process/50)
    max_transfers = math.ceil(11*96/50)
    vol_per_transfer = 11*number_of_samples_to_process/num_transfers_each

    max_mm_ind = 0
    p50.pick_up_tip()
    for reagent in [blt, tb1]:
        r_ind_prev = 0
        for i in range(num_transfers_each):
            r_ind = i*len(reagent)//max_transfers
            mm_ind = i*len(mm)//max_transfers
            if r_ind != r_ind_prev:
                p50.transfer(
                    10, reagent[r_ind], mm[mm_ind].bottom(5), new_tip='never')
                r_ind_prev = r_ind
            if mm_ind > max_mm_ind:
                max_mm_ind = mm_ind
            p50.transfer(
                vol_per_transfer,
                reagent[r_ind],
                mm[mm_ind].bottom(5),
                new_tip='never'
            )
            if reagent == tb1:
                p50.blow_out()
            p50.move_to(mm[mm_ind].top(10))

    # mix used mastermix tubes
    p50.flow_rate.aspirate = 40
    for tube in mm[:max_mm_ind+1]:
        for i in range(10):
            p50.aspirate(50, tube)
            p50.dispense(50, tube.bottom(15))
        p50.blow_out(tube.top())

    # distribute mastermix
    p50.flow_rate.aspirate = 25
    if using_p50_multi == 'no':
        for i, s in enumerate(samples):
            if not p50.hw_pipette['has_tip']:
                p50.pick_up_tip()
            mm_ind = i//48
            p50.transfer(20, mm[mm_ind], s, new_tip='never')
            p50.mix(10, 15, s)
            p50.blow_out()
            p50.drop_tip()

    else:
        mm_plate = ctx.load_labware(
            'biorad_96_wellplate_200ul_pcr',
            '3',
            'mastermix plate (for multi-channel transfer)'
        )
        tips50m = ctx.load_labware('opentrons_96_tiprack_300ul', '6')
        m50 = ctx.load_instrument(
            'p50_multi',
            mount=p50_multi_mount_if_applicable,
            tip_racks=[tips50m]
        )
        num_cols = math.ceil(number_of_samples_to_process/8)
        samples_multi = rxn_plate.rows()[0][:num_cols]

        # transfer mm to plate columns
        for i in range(num_cols):
            for j, well in enumerate(mm_plate.columns()[i//6]):
                well_ind = i*8+j
                mm_ind = well_ind//48
                if not p50.hw_pipette['has_tip']:
                    p50.pick_up_tip()
                p50.transfer(21, mm[mm_ind], well, new_tip='never')
                p50.blow_out()
        p50.drop_tip()

        # distribute mm to sample columns
        for dest in samples_multi:
            source = mm_plate.rows()[0][i//6]
            m50.pick_up_tip()
            m50.transfer(20, source, dest, new_tip='never')
            m50.mix(10, 20, dest)
            m50.blow_out(dest.top())
            m50.drop_tip()

    ctx.comment('Seal the plate and thermocycle running the TAG program.')
