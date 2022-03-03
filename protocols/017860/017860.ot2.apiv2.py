from opentrons import protocol_api
import csv
import math

metadata = {
    'protocolName': 'CSV Plate Filling',
    'author': 'Nick <protocols@opentrons.com>',
    'source': 'Custom Protocol Request',
    'apiLevel': '2.11'
}


def run(ctx: protocol_api.ProtocolContext):

    [input_csv,
     tiprack_lname_20_ul,
     tiprack_lname_300ul,
     n_plates
     ] = get_values(  # noqa: F821
     "input_csv",
     "tiprack_lname_20_ul",
     "tiprack_lname_300ul",
     "n_plates"
     )

    if not 0 < n_plates < 7:
        raise Exception(("The number of plates are {}, but should be between "
                         "one to six").format(n_plates))

    # update the path to your transfer CSV on the robot
    # REVIEW: I think the user used to have to manually edit this to get the
    # desired input file. I modernized it so that it's loaded through
    # fields.json, but that changes their workflow. Keep or not?
    # transfer_info_csv_path = "data/csv/rr027-M9_singlesCheck.csv"

    plate_name = 'nunc_96_wellplate_400ul'

    # labware
    plates = [ctx.load_labware(plate_name, str(slot+1))
              for slot in range(n_plates)]
    tuberack_15_50 = ctx.load_labware(
        'opentrons_10_tuberack_falcon_4x50ml_6x15ml_conical', '8')
    tuberacks_15 = \
        [ctx.load_labware('opentrons_15_tuberack_falcon_15ml_conical', slot)
         for slot in ['9', '7']]
    tips_20 = [ctx.load_labware('opentrons_96_tiprack_20ul', '10')]
    tips_300 = [ctx.load_labware('opentrons_96_tiprack_300ul', '11')]

    p20 = ctx.load_instrument(
                              'p20_single_gen2',
                              'left',
                              tip_racks=tips_20
                              )
    p300 = ctx.load_instrument(
                              'p300_single_gen2',
                              'right',
                              tip_racks=tips_300
                              )

    p20.flow_rate.aspirate = 100
    p20.flow_rate.dispense = 1000
    p300.flow_rate.aspirate = 100
    p300.flow_rate.dispense = 1000

    # New csv parsing functions for csv input as string from protocol web
    # interface/fields.json
    def csv_string_to_list(csv_string):
        new_list = []
        rows = csv_string.split()
        new = csv.reader(rows)
        for row in new:
            new_list.append(row)
        new_list = new_list[1:]
        reordered = []
        # Transform rows -> columns
        for col in range(len(new_list[0])):
            temp = []
            for row in new_list:
                temp.append(row[col])
            reordered.append(temp)
        return reordered

    # CSV parsing function
    # Old function for reading csv from a file
    def csv_to_list(file_path):
        new_list = []
        with open(file_path, 'r') as csvfile:
            new = csv.reader(csvfile)
            for row in new:
                new_list.append(row)
        new_list = new_list[1:]
        reordered = []
        # Transform rows -> columns
        for col in range(len(new_list[0])):
            temp = []
            for row in new_list:
                temp.append(row[col])
            reordered.append(temp)
        return reordered

    # parses through CSV for transfer data
    csv_info = csv_string_to_list(input_csv)
    csv_info.pop(0)  # First csv column is identifiers I think.

    # set up list of all wells
    all_wells = [well for plate in plates for well in plate.wells()]

    # set up list of all source tubes
    # check volume of media necessary and change length of medias accordingly
    # The number of drug tubes is the length of the CSV rows minus the entry
    # for media once the identifier column has been popped off.
    NUM_DRUGS = len(csv_info) - 1
    if not 0 < NUM_DRUGS < 37:
        raise Exception(("The number of antibiotic tubes + barcoding dye tube "
                         "are {}, as defined by the csv, but should be "
                         "between 1 to 36, please check the number of columns "
                         "in your input csv file").
                        format(NUM_DRUGS))
    media_tubes = tuberack_15_50.wells_by_name()
    medias = [media_tubes['A3'], media_tubes['B3'], media_tubes['A4']]
    # For a maximum number of 3 antibiotic tubes on the 15/50 mL tuberack
    # 15*2 refers to the number of drug tubes that fit on the two 15 ml
    # tuberacks (i.e. 15 each)
    drugs1 = None
    if NUM_DRUGS > 15*2:
        drugs1 = tuberack_15_50.wells()[0:NUM_DRUGS-15*2]
    drugs2 = [tube for rack in tuberacks_15 for tube in rack.wells()]
    # run through all of the full 15mL racks before going back
    # to tuberack_15_50
    # barcode dye is the last tube (C1) of the 15/50 rack
    drugs = drugs2 + drugs1 if drugs1 is not None else drugs2

    # well height and volume tracking function
    well_V_track = [0 for _ in range(len(plates)*96)]
    well_h_track = [-0.4 for _ in range(len(plates)*96)]
    well_r = 3.43
    pi = math.pi

    def well_height_track(well_ind, vol):
        nonlocal well_V_track
        nonlocal well_h_track
        nonlocal well_r

        dh = vol/(pi*(well_r**2))
        well_h_track[well_ind] += dh

    # media height and volume tracking function
    media = medias[0]
    num_medias = 3
    start_medias = 0
    media_V_track = 70000
    media_h_track = -16
    media_r_cyl = 13.5

    def media_height_track(vol):
        """
        Keeps track of the three media tubes volume height, and when to switch
        tubes when the current tube runs too low
        """

        nonlocal media_V_track
        nonlocal media_h_track
        nonlocal media
        nonlocal num_medias
        nonlocal start_medias

        media_V_track -= vol
        # change and reset media tube if necessary
        if media_V_track < 500:
            num_medias -= 1
            if num_medias == 0:
                ctx.pause("Please replace two 50ml media tubes filled to "
                          "50ml line before resuming.")
                media = medias[0]
            else:
                start_medias += 1
                media = medias[start_medias]
            media_V_track = 70000
            media_h_track = -16

        dh = (0.70*vol)/(pi*(media_r_cyl**2))
        media_h_track -= dh

    # initialize volume and height trackers, assuming that reagents are filled
    # to 14ml line in standard 15ml tube
    drug_V_track = [14000 for _ in range(NUM_DRUGS)]
    drug_h_track = [-24 for _ in range(NUM_DRUGS)]
    drug_r_cyl = 7.52
    drug_r_cone = [7.52 for _ in range(NUM_DRUGS)]
    drug_h_cone = 21.35
    theta = math.atan(drug_r_cyl/drug_h_cone)
    tan = math.tan(theta)
    cone_vol = pi*(drug_r_cyl**2)*drug_h_cone/3

    def drug_height_track(drug_ind, vol):
        nonlocal drug_V_track
        nonlocal drug_h_track
        nonlocal drug_r_cone

        # check that there is sufficient drug left in the tube
        if drug_V_track[drug_ind] - vol < 100:
            ctx.pause("Please fill drug %d to the 14ml line and replace in "
                      "its proper well before resuming." % (drug_ind+1))
            drug_V_track[drug_ind] = 14000
            drug_h_track = -24

        # calculates height to aspirate from if in main cylinder of tube
        if drug_V_track[drug_ind] >= cone_vol:
            drug_V_track[drug_ind] -= vol
            dh = vol/(pi*(drug_r_cyl**2))
            drug_h_track[drug_ind] -= dh

        # calculates height to aspirate from if in cone at bottom of tube
        else:
            new_h = math.pow((drug_V_track[drug_ind]-vol)/(pi/3*(tan**2)), 1/3)
            dh = drug_h_track[drug_ind] - new_h
            drug_h_track[drug_ind] -= dh
            drug_V_track[drug_ind] -= vol
            drug_r_cone[drug_ind] = new_h*tan

    # calculate number of deck fills and initialize counter
    num_wells = len(plates)*96
    num_deck_fills = math.ceil(len(csv_info[0])/num_wells)
    num_total_transfers = len(csv_info[0])

    # perform full deck transfer
    for fill in range(num_deck_fills):

        # define CSV indices that will receive transfer on this deck set
        block_ind = range(fill*num_wells, (fill+1)*num_wells)

        p300.pick_up_tip()
        p20.pick_up_tip()

        # set proper tube and height to aspirate from, and initialize volumes
        # and aspirate for distribution
        media_height_track(300)
        p300.aspirate(300, media.top(media_h_track))
        pip_300_v_track = 300

        media_height_track(20)
        p20.aspirate(20, media.top(media_h_track))
        pip_50_v_track = 20

        # Transfer media to wells
        for i, (ind, well) in enumerate(zip(block_ind, all_wells)):
            if ind == num_total_transfers:
                break
            v = float(csv_info[0][ind])

            # choose pipette
            if v <= 20 and v > 0:
                # check volume in pipette
                if v > pip_50_v_track - 5:
                    p20.blow_out(media.top())
                    media_height_track(20)
                    p20.aspirate(20, media.top(media_h_track))
                    pip_50_v_track = 20

                # perform transfer
                well_height_track(i, v)
                p20.dispense(v, well.bottom(-0.4))
                pip_50_v_track -= v

            elif v > 20:
                if v > pip_300_v_track - 5:
                    p300.blow_out(media.top())
                    media_height_track(300)
                    p300.aspirate(300, media.top(media_h_track))
                    pip_300_v_track = 300

                # perform transfer
                well_height_track(i, v)
                p300.dispense(v, well.bottom(-0.4))
                pip_300_v_track -= v

                # touch tip here if necessary

        p300.drop_tip()
        p20.drop_tip()

        # perform drugs transfer
        for drug_ind, drug in enumerate(drugs):
            # range of drug transfers always between 5 and 50ul
            p20.pick_up_tip()

            # initialize volumes and aspirate for distribution
            drug_height_track(drug_ind, 20)
            p20.aspirate(20, drug.top(drug_h_track[drug_ind]))
            pip_v_track = 20

            # loop and distribute drug in proper amounts
            for i, (ind, well) in enumerate(zip(block_ind, all_wells)):
                if ind == num_total_transfers:
                    break
                drug_transfers = csv_info[drug_ind+1]
                v = float(drug_transfers[ind])

                # only begin transfer process if volume is more than 0ul
                if v > 0:
                    # check if volume in pipette tip can accommodate transfer
                    if v > pip_v_track - 5:
                        p20.blow_out(drug.top())
                        drug_height_track(drug_ind, 20)
                        p20.aspirate(20, drug.top(drug_h_track[drug_ind]))
                        pip_v_track = 20

                    # perform transfer
                    # REVIEW: I think this was left here for debugging in the
                    # original protocol
                    # print(str(well_h_track[i]))
                    well_height_track(i, v)
                    p20.dispense(v, well.bottom(well_h_track[i]))
                    pip_v_track -= v

                    # REVIEW: Commented out in the original protocol
                    # touch tip if necessary
                    # drop1 = well.from_center(h=-0.2, theta=0, r=0)
                    # drop2 = well.from_center(h=1.5, theta=0, r=0)
                    # down = (well, drop1)
                    # up = (well, drop2)
                    # p10.move_to(up)
                    # p10.move_to(down)

            # return tip to corresponding well for future deck refills
            p20.return_tip()

        if fill < num_deck_fills-1:
            ctx.pause(("Please remove all sample plates from the deck and "
                      "replace tips in the first {} wells of the tiprack "
                       "before resuming.").format(NUM_DRUGS))
            p20.reset_tipracks()
            p300.reset_tipracks()
