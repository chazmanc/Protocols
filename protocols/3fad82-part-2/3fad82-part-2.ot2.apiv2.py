import math

metadata = {
    'protocolName': '''Quarter Volume NEBNext Ultra II DNA Library Prep Kit
    for Illumina: part 2 - purification of samples and PCR''',
    'author': 'Steve Plonk <protocols@opentrons.com>',
    'apiLevel': '2.9'
}


def run(ctx):

    # get parameter values from json above
    [sample_count, labware_tips300, labware_tips20, labware_pcr_plate,
     clearance_reservoir, clearance_samp_plate, flow_rate_beads, delay_beads,
     engage_height, engage_time, dry_time
     ] = get_values(  # noqa: F821
      'sample_count', 'labware_tips300', 'labware_tips20', 'labware_pcr_plate',
      'clearance_reservoir', 'clearance_samp_plate', 'flow_rate_beads',
      'delay_beads', 'engage_height', 'engage_time', 'dry_time')

    ctx.set_rail_lights(True)

    # tips, p20 multi gen2, p300 multi gen2
    tips20 = [ctx.load_labware(
     labware_tips20, str(slot)) for slot in [2, 3, 5]]
    p20m = ctx.load_instrument(
        "p20_multi_gen2", 'left', tip_racks=tips20)
    tips300 = [ctx.load_labware(labware_tips300, str(slot)) for slot in [6, 9]]
    p300m = ctx.load_instrument(
        "p300_multi_gen2", 'right', tip_racks=tips300)

    """
    helper functions
    """
    def pause_attention(message):
        ctx.set_rail_lights(False)
        ctx.delay(seconds=10)
        ctx.pause(message)
        ctx.set_rail_lights(True)

    def aspirate_with_delay(current_pipette, volume, source, delay_seconds):
        current_pipette.aspirate(volume, source)
        if delay_seconds > 0:
            ctx.delay(seconds=delay_seconds)

    def dispense_with_delay(current_pipette, volume, dest, delay_seconds):
        current_pipette.dispense(volume, dest)
        if delay_seconds > 0:
            ctx.delay(seconds=delay_seconds)

    def mix_with_delay(current_pipette, volume, location, delay_seconds):
        current_pipette.aspirate(volume, location)
        if delay_seconds > 0:
            ctx.delay(seconds=delay_seconds)
        current_pipette.dispense(volume, location)
        if delay_seconds > 0:
            ctx.delay(seconds=delay_seconds)

    def slow_tip_withdrawal(current_pipette, well_location, to_center=False):
        if current_pipette.mount == 'right':
            axis = 'A'
        else:
            axis = 'Z'
        ctx.max_speeds[axis] = 10
        if to_center is False:
            current_pipette.move_to(well_location.top())
        else:
            current_pipette.move_to(well_location.center())
        ctx.max_speeds[axis] = None

    def pre_wet(current_pipette, volume, location):
        for rep in range(2):
            current_pipette.aspirate(volume, location)
            current_pipette.dispense(volume, location)

    def set_default_clearances(
     current_pipette, aspirate_setting, dispense_setting):
        if 0 < aspirate_setting < 5 and 0 < dispense_setting < 5:
            current_pipette.well_bottom_clearance.aspirate = aspirate_setting
            current_pipette.well_bottom_clearance.dispense = dispense_setting

    def restore_default_clearances(current_pipette):
        current_pipette.well_bottom_clearance.aspirate = 1
        current_pipette.well_bottom_clearance.dispense = 1

    def viscous_flow_rates(current_pipette):
        current_pipette.flow_rate.aspirate = flow_rate_beads
        current_pipette.flow_rate.dispense = flow_rate_beads
        current_pipette.flow_rate.blow_out = flow_rate_beads

    def etoh_flow_rates(current_pipette):
        if (current_pipette.name == 'p300_multi_gen2' or
           current_pipette.name == 'p300_single_gen2'):
            current_pipette.flow_rate.aspirate = 92.86
            current_pipette.flow_rate.dispense = 92.86
            current_pipette.flow_rate.blow_out = 300

    def default_flow_rates(current_pipette):
        if (current_pipette.name == 'p300_multi_gen2' or
           current_pipette.name == 'p300_single_gen2'):
            current_pipette.flow_rate.aspirate = 92.86
            current_pipette.flow_rate.dispense = 92.86
            current_pipette.flow_rate.blow_out = 92.86
        elif (current_pipette.name == 'p20_multi_gen2' or
              current_pipette.name == 'p20_single_gen2'):
            current_pipette.flow_rate.aspirate = 7.56
            current_pipette.flow_rate.dispense = 7.56
            current_pipette.flow_rate.blow_out = 7.56

    def reuse_tips(current_pipette, which_tips):
        current_pipette.reset_tipracks()
        current_pipette.starting_tip = named_tips[which_tips]

    named_tips = {}

    def name_the_tips(tip_box, name_list, well_list):
        for name, well in zip(
         name_list, well_list):
            named_tips[name] = tip_box[well]

    ctx.delay(seconds=10)
    pause_attention("""
    Set up for part 2: Remove master mix plate and used tip boxes.
    Move sample plate to magnetic module. PCR plate (8.7 ul PCR master mix
    with indexes) on cycler, reagent reservoir in deck slot 1, p20 tips
    in slots 2, 3 and 5, p300 tips in slots 6 and 9.
    """)

    ctx.comment("""
    reagent reservoir in deck slot 1:
    col 1 - beads
    col 2 - 80% ethanol
    col 4 - water
    col 12 - waste
    """)
    reagent_reservoir = ctx.load_labware(
     'nest_12_reservoir_15ml', '1', 'Reagent Reservoir')
    [beads, etoh, water, waste] = [reagent_reservoir.wells_by_name()[
     well] for well in ['A1', 'A2', 'A4', 'A12']]

    ctx.comment("""
    sample plate on magnetic module:
    samples arranged in columns of 8
    up to 96 samples total
    {} samples in this run
    """.format(str(sample_count)))
    num_cols = math.ceil(sample_count / 8)
    mag = ctx.load_module('magnetic module', '4')
    mag.disengage()
    sample_plate = mag.load_labware(labware_pcr_plate, 'Sample Plate')

    ctx.comment("""
    PCR plate on cycler:
    containing 8.7 ul PCR master mix with indexes
    """)
    tc = ctx.load_module('thermocycler')
    tc.open_lid()
    pcr_plate = tc.load_labware(labware_pcr_plate, 'Sample Plate')

    ctx.comment("""
    transfer beads to sample plate
    wait, engage magnet, wait

    liquid handling method for beads:
    slow flow rate for aspiration and dispense
    wait for liquid to finish moving after aspiration and dispense
    dispense to a surface
    withdraw tip slowly from liquid
    """)

    viscous_flow_rates(p20m)
    for column in sample_plate.columns()[:num_cols]:
        p20m.pick_up_tip()
        aspirate_with_delay(p20m, 9.5, beads.bottom(
         clearance_reservoir), delay_beads)
        slow_tip_withdrawal(p20m, beads)
        dispense_with_delay(p20m, 9.5, column[0].bottom(
         clearance_samp_plate), delay_beads)
        for repeat in range(5):
            mix_with_delay(p20m, 10, column[0].bottom(
             clearance_samp_plate), delay_beads)
        p20m.drop_tip()
    default_flow_rates(p20m)
    ctx.delay(minutes=5)
    mag.engage(height=engage_height)
    ctx.delay(minutes=engage_time)

    ctx.comment("""
    remove supernatant from beads
    """)
    for column in sample_plate.columns()[:num_cols]:
        p20m.transfer(19, column[0].bottom(
         clearance_samp_plate), waste.top(), new_tip='always')

    ctx.comment("""
    wash beads twice with 80 percent ethanol
    return tips for reuse with 2nd wash

    liquid handling method for ethanol:
    fast flow rate for blow out
    pre-wet the tips twice (saturate air)
    15 ul air gap
    dispense from top
    no tip touch (tip reuse)
    delayed blowout after dispense (let etoh fall to bottom of tip first)
    repeat blowout (for complete dispense)
    """)
    etoh_flow_rates(p300m)
    for wash in range(2):
        if wash == 0:
            name_the_tips(tips300[0], ['etoh_tips'], [
             tips300[0].next_tip().well_name])
        else:
            reuse_tips(p300m, 'etoh_tips')
        p300m.pick_up_tip()
        for column in sample_plate.columns()[:num_cols]:
            if wash == 0:
                pre_wet(p300m, 100, etoh.bottom(2))
            p300m.aspirate(100, etoh.bottom(2))
            p300m.air_gap(15)
            p300m.dispense(115, column[0].top())
            for rep in range(3):
                if rep > 0:
                    p300m.aspirate(200, column[0].top())
                ctx.delay(seconds=1)
                p300m.blow_out(column[0].top())
        if wash == 0:
            p300m.return_tip()
            name_the_tips(tips300[0], ['sup_tips'], [
             tips300[0].next_tip().well_name])
            p300m.transfer(100, [column[0].bottom(
             clearance_samp_plate) for column in sample_plate.columns()[
             :num_cols]], waste.top(), air_gap=15, new_tip='always',
             trash=False)
        else:
            p300m.drop_tip()
            reuse_tips(p300m, 'sup_tips')
            p300m.transfer(100, [column[0].bottom(
             clearance_samp_plate) for column in sample_plate.columns()[
             :num_cols]], waste.top(), air_gap=15, new_tip='always')
    default_flow_rates(p300m)

    ctx.comment("""
        let beads air dry
        """)
    ctx.delay(minutes=dry_time)
    mag.disengage()

    ctx.comment("""
        add water to beads and mix
        wait
        engage magnet
        wait
        """)
    p20m.transfer(5, water.bottom(clearance_reservoir), [column[0].bottom(
     clearance_samp_plate) for column in sample_plate.columns()[
     :num_cols]], mix_after=(4, 5), new_tip='always')
    ctx.delay(minutes=2)
    mag.engage(height=engage_height)
    ctx.delay(minutes=engage_time)

    ctx.pause("""
    Please remove all tip boxes from the deck and place one fresh box of
    p20 tips in deck slot 2.
    """)
    p20m.reset_tipracks()

    ctx.comment("""
        transfer eluate to PCR plate and mix
        """)
    p20m.transfer(3.75, [column[0].bottom(
     clearance_samp_plate) for column in sample_plate.columns()[
     :num_cols]], [column[0].bottom(
      clearance_samp_plate) for column in pcr_plate.columns()[
      :num_cols]], mix_after=(3, 5), new_tip='always')

    ctx.comment("""
        PCR cycling:

        30 sec 98 C

        repeat 10 cycles:
        10 sec 90 C
        75 sec 65 C

        5 min 65 C
        hold 4 C

        """)

    profiles = [
     [{'temperature': temp, 'hold_time_seconds': sec} for temp, sec in zip(
      [98], [30])], [
      {'temperature': temp, 'hold_time_seconds': sec} for temp, sec in zip(
       [90, 65], [10, 75])], [
      {'temperature': temp, 'hold_time_seconds': sec} for temp, sec in zip(
       [65], [300])]]

    tc.close_lid()
    tc.set_lid_temperature(100)
    for profile, reps in zip(profiles, [1, 10, 1]):
        tc.execute_profile(
         steps=profile, repetitions=reps, block_max_volume=12)
    tc.set_block_temperature(4)
    tc.deactivate_lid()
    pause_attention("""Process steps and PCR cycling for part 2 are complete.
    Click resume to open the cycler and finish the protocol run. Please proceed
    to part 3.""")
    tc.open_lid()
    tc.deactivate_block()
