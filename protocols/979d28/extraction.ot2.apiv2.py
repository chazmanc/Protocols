# flake8: noqa
import sys
import serial
from opentrons.types import Point
import math

metadata = {
    'protocolName': 'Omega Mag-Bind® Total RNA Isolation',
    'author': 'Opentrons <protocols@opentrons.com>',
    'apiLevel': '2.12'
}

TEST_MODE = False


# Start protocol
def run(ctx):

    [num_samples, mixreps, elution2_vol] = get_values(
        'num_samples', 'mixreps', 'vol_elution_final')

    if not ctx.is_simulating():
        sys.path.append("/var/lib/jupyter/notebooks/")
        import bioshake
        import labware_modifier

    vol_mix = 180
    z_offset = 1.0
    radial_offset_fraction = 0.5  # fraction of radius
    starting_vol = 400
    binding_buffer_vol = 320
    vhb_vol = 400
    rna_wash1_vol = 400
    rna_wash2_vol = 300
    elution1_vol = 100
    dnase_vol = 52
    phm_vol = 150
    settling_time = 3  # if not TEST_MODE else 0  # minutes

    ctx.max_speeds['X'] = 200
    ctx.max_speeds['Y'] = 200

    if not ctx.is_simulating():
        my_bioshake = bioshake.BioshakeDriver()
    bioshake_plate = ctx.load_labware('nestbioshake_96_wellplate_2000ul', '1')

    magdeck = ctx.load_module('magnetic module gen2', '6')
    magdeck.disengage()
    magplate = magdeck.load_labware('nest_96_wellplate_2ml_deep',
                                    'deepwell plate')
    tempdeck = ctx.load_module('Temperature Module Gen2', '9')
    elutionplate = tempdeck.load_labware(
                'vwr_96_aluminumblock_200ul',
                'elution plate')
    res1 = ctx.load_labware('nest_12_reservoir_15ml', '2',
                            'reagent reservoir 1')
    res2 = ctx.load_labware('nest_12_reservoir_15ml', '5',
                            'reagent reservoir 2')
    waste = ctx.load_labware('nest_1_reservoir_195ml', '3',
                             'Liquid Waste').wells()[0].top()

    num_cols = math.ceil(num_samples/8)
    tips300 = [ctx.load_labware('opentrons_96_filtertiprack_200ul', slot,
                                '200µl filtertiprack')
               for slot in ['7', '8', '10', '11'][
                :math.ceil((num_cols*8)/12)]]

    # load P300M pipette
    m300 = ctx.load_instrument(
        'p300_multi_gen2', 'right', tip_racks=tips300)

    """
    Here is where you can define the locations of your reagents.
    """
    binding_buffer = res1.wells()[:2]
    elution_solution = res1.wells()[11:]
    vhb = res1.wells()[3:5]
    rna_wash = [res2.wells()[s:f] for s, f in [[0, 2], [2, 4], [4, 6]]]
    dnase = res1.wells()[6:7]
    phm = res1.wells()[8:9]

    mag_samples_m = magplate.rows()[0][3:3+num_cols]
    shake_samples_m = bioshake_plate.rows()[0][3:3+num_cols]
    elution_samples_m = elutionplate.rows()[0][:num_cols]
    all_tips = [well for rack in tips300 for well in rack.rows()[0]]
    parking_sets = [all_tips[i*num_cols:(i+1)*num_cols] for i in range(8)]
    radius = mag_samples_m[0].width/2

    magdeck.disengage()  # just in case
    if not TEST_MODE:
        tempdeck.set_temperature(4)

    waste_vol = 0
    waste_threshold = 185000

    def remove_supernatant(vol, parking_spots, park=False):
        """
        `remove_supernatant` will transfer supernatant from the deepwell
        extraction plate to the liquid waste reservoir.
        :param vol (float): The amount of volume to aspirate from all deepwell
                            sample wells and dispense in the liquid waste.
        :param park (boolean): Whether to pick up sample-corresponding tips
                               in the 'parking rack' or to pick up new tips.
        """

        def _waste_track(vol):
            nonlocal waste_vol
            if waste_vol + vol >= waste_threshold:
                # Setup for flashing lights notification to empty liquid waste
                ctx.home()
                ctx.pause('Please empty liquid waste before resuming.')
                waste_vol = 0
            waste_vol += vol

        m300.flow_rate.aspirate /= 5
        for m, spot in zip(mag_samples_m, parking_spots):
            m300.pick_up_tip(spot)
            _waste_track(vol)
            num_trans = math.ceil(vol/200)
            vol_per_trans = vol/num_trans
            for _ in range(num_trans):
                m300.transfer(vol_per_trans, m.bottom(0.8), waste, new_tip='never')
                m300.blow_out(waste)
            m300.air_gap(5)
            m300.drop_tip(spot)
        m300.flow_rate.aspirate *= 5

    def resuspend(location, reps=mixreps, vol=vol_mix, method='mix', samples=mag_samples_m):

        if method == 'shake':
            pass
        elif 'mix' in method:
            m300.flow_rate.aspirate *= 4
            m300.flow_rate.dispense *= 4
            side = 1 if samples.index(location) % 2 == 0 else -1
            bead_loc = location.bottom().move(
                Point(x=side*radius*radial_offset_fraction, z=z_offset))
            m300.move_to(location.center())
            for _ in range(reps):
                m300.aspirate(vol, bead_loc)
                m300.dispense(vol, bead_loc)
            m300.flow_rate.aspirate /= 4
            m300.flow_rate.dispense /= 4

    def bind(vol, parking_spots, samples=mag_samples_m):
        """
        `bind` will perform magnetic bead binding on each sample in the
        deepwell plate. Each channel of binding beads will be mixed before
        transfer, and the samples will be mixed with the binding beads after
        the transfer. The magnetic deck activates after the addition to all
        samples, and the supernatant is removed after bead bining.
        :param vol (float): The amount of volume to aspirate from the elution
                            buffer source and dispense to each well containing
                            beads.
        :param park (boolean): Whether to save sample-corresponding tips
                               between adding elution buffer and transferring
                               supernatant to the final clean elutions PCR
                               plate.
        """
        latest_chan = -1
        chan_ind = 0
        max_vol_per_chan = 0.95*res1.wells()[0].max_volume
        cols_per_source_chan = math.ceil(6/len(binding_buffer))
        for i, (well, spot) in enumerate(zip(samples, parking_spots)):
            m300.pick_up_tip(spot)
            chan_ind = i//cols_per_source_chan
            src = binding_buffer[chan_ind]
            if chan_ind != latest_chan:  # mix if accessing new channel
                reps = 5 if not TEST_MODE else 1
                for _ in range(reps):
                    m300.aspirate(180, src.bottom(0.5))
                    m300.dispense(180, src.bottom(5))
                latest_chan = chan_ind
            m300.transfer(vol, src, well.top(), new_tip='never')
            # m300.mix(mixreps, vol_mix, well.bottom(2))
            m300.air_gap(5)
            m300.drop_tip(spot)

        # ctx.pause('Place deepwell plate on Bioshake.')
        shake_time = 300  # if not TEST_MODE else 5
        m300.home()
        if not ctx.is_simulating():
            my_bioshake.set_shake(1500, shake_time)
            my_bioshake.home_shaker()

        ctx.pause('Place deepwell plate on magnetic module when \
shaking is complete.')

        magdeck.engage()
        ctx.delay(minutes=settling_time, msg=f'Incubating on MagDeck for \
{settling_time} minutes.')

        # remove initial supernatant
        remove_supernatant(vol+starting_vol, parking_spots)

    def wash(vol, source, parking_spots, remove=True,
             resuspend_method='mix', supernatant_volume=None,
             samples=mag_samples_m, shake_time=5, resuspend_vol=None):
        """
        `wash` will perform bead washing for the extraction protocol.
        :param vol (float): The amount of volume to aspirate from each
                            source and dispense to each well containing beads.
        :param source (List[Well]): A list of wells from where liquid will be
                                    aspirated. If the length of the source list
                                    > 1, `wash` automatically calculates
                                    the index of the source that should be
                                    accessed.
        :param mix_reps (int): The number of repititions to mix the beads with
                               specified wash buffer (ignored if resuspend is
                               False).
        :param park (boolean): Whether to save sample-corresponding tips
                               between adding wash buffer and removing
                               supernatant.
        :param resuspend (boolean): Whether to resuspend beads in wash buffer.
        """

        if magdeck.status == 'engaged':
            magdeck.disengage()

        if resuspend_method == 'shake' and source == elution_solution:
            if not TEST_MODE:
                ctx.delay(minutes=5, msg='Air drying for 5 minutes.')
            ctx.pause('Place deepwell plate on Bioshake before resuming.')

        cols_per_source_chan = math.ceil(6/len(source))
        if source == vhb:
            num_trans = math.ceil(vol/180)
            air_gap_vol = 20
        else:
            num_trans = math.ceil(vol/200)
            air_gap_vol = None
        vol_per_trans = vol/num_trans
        for i, (well, spot) in enumerate(zip(samples, parking_spots)):
            m300.pick_up_tip(spot)
            src = source[i//cols_per_source_chan]
            for n in range(num_trans):
                m300.dispense(m300.current_volume, src.top())
                m300.aspirate(vol_per_trans, src)
                if source == vhb:
                    ctx.max_speeds['Z'] = 20
                    ctx.max_speeds['A'] = 20
                m300.move_to(src.top())
                if source == vhb:
                    ctx.delay(seconds=2)
                    ctx.max_speeds['Z'] = None
                    ctx.max_speeds['A'] = None
                if air_gap_vol:
                    m300.aspirate(air_gap_vol, src.top())
                m300.dispense(m300.current_volume, well.top())
                if n < num_trans - 1:
                    m300.aspirate(10, well.top())
            resus_vol = resuspend_vol if resuspend_vol else vol_mix
            resuspend(well, mixreps, resus_vol, method=resuspend_method, samples=samples)
            m300.blow_out(well.top())
            m300.air_gap(5)
            m300.drop_tip(spot)

        if 'shake' in resuspend_method:
            ctx.comment(f'Shaking for {shake_time} minutes at 1000rpm.')
            m300.home()
            if not ctx.is_simulating():
                # actual_shake_time = 10 if TEST_MODE else shake_time*60  # minutes to seconds
                actual_shake_time = shake_time*60
                my_bioshake.set_shake(1000, actual_shake_time)
                my_bioshake.home_shaker()
                ctx.delay(seconds=actual_shake_time+10)

        if remove:
            if magdeck.status == 'disengaged':
                magdeck.engage()

            ctx.delay(minutes=settling_time, msg=f'Incubating on MagDeck for \
{settling_time} minutes.')

            removal_vol = supernatant_volume if supernatant_volume else vol
            remove_supernatant(removal_vol, parking_spots)

    def elute(vol, parking_spots):
        """
        `elute` will perform elution from the deepwell extractton plate to the
        final clean elutions PCR plate to complete the extraction protocol.
        :param vol (float): The amount of volume to aspirate from the elution
                            buffer source and dispense to each well containing
                            beads.
        :param park (boolean): Whether to save sample-corresponding tips
                               between adding elution buffer and transferring
                               supernatant to the final clean elutions PCR
                               plate.
        """

        # resuspend beads in elution
        if magdeck.status == 'enagaged':
            magdeck.disengage()

        ctx.pause('Place deepwell plate on Bioshake before resuming.')

        for i, (m, spot) in enumerate(zip(shake_samples_m, parking_spots)):
            m300.pick_up_tip(spot)
            m300.transfer(vol, elution_solution[0], m, new_tip='never')
            m300.air_gap(5)
            m300.drop_tip(spot)

        if not ctx.is_simulating():
            # actual_shake_time = 10 if TEST_MODE else 300  # minutes to seconds
            actual_shake_time = 300
            my_bioshake.set_shake(1000, actual_shake_time)
            my_bioshake.home_shaker()
        ctx.pause('Move plate back to magnetic module.')

        magdeck.engage()
        ctx.delay(minutes=settling_time, msg=f'Incubating on MagDeck for \
{settling_time} minutes.')

        m300.flow_rate.aspirate /= 5
        for i, (m, e, spot) in enumerate(
                zip(mag_samples_m, elution_samples_m, parking_spots)):
            m300.pick_up_tip(spot)
            m300.transfer(vol-5, m.bottom(1.2), e.bottom(5), air_gap=20,
                          new_tip='never')
            m300.blow_out(e.top(-2))
            m300.air_gap(5)
            m300.drop_tip(spot)

    bind(binding_buffer_vol, parking_spots=parking_sets[0],
         samples=shake_samples_m)
    wash(vhb_vol, vhb, parking_spots=parking_sets[1])
    wash(rna_wash1_vol, rna_wash[0], parking_spots=parking_sets[2])
    if not TEST_MODE:
        ctx.delay(minutes=5)
    wash(elution1_vol, elution_solution, parking_spots=parking_sets[3],
         remove=False, samples=shake_samples_m, resuspend_method='shake',
         shake_time=5)
    wash(dnase_vol, dnase, parking_spots=parking_sets[4], remove=False,
         samples=shake_samples_m, resuspend_method='mix', resuspend_vol=120)
    if not TEST_MODE:
        ctx.delay(minutes=10)
    wash(phm_vol, phm, parking_spots=parking_sets[5], remove=False,
         samples=shake_samples_m, resuspend_method='shake', shake_time=1)
    if not TEST_MODE:
        ctx.delay(minutes=1)
    wash(rna_wash2_vol, rna_wash[1], parking_spots=parking_sets[6],
         samples=shake_samples_m, resuspend_method='shakemix', shake_time=10,
         remove=False)
    ctx.pause('Place deepwell plate on magnetic module before resuming.')
    magdeck.engage()
    ctx.delay(minutes=settling_time, msg=f'Incubating on MagDeck for \
{settling_time} minutes.')
    remove_supernatant(parking_spots=parking_sets[6], vol=600)
    wash(rna_wash1_vol, rna_wash[2], parking_spots=parking_sets[7])
    if not TEST_MODE:
        ctx.delay(minutes=10, msg='Air drying')
    elute(elution2_vol, parking_spots=parking_sets[3])
