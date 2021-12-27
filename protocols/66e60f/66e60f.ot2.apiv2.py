from opentrons import protocol_api
import re

metadata = {
    'protocolName': '66e60f - Normalization protocol',
    'author': 'Eskil Andersen <eskil.andersen@opentrons.com>',
    'source': 'Custom Protocol Request',
    'apiLevel': '2.11'   # CHECK IF YOUR API LEVEL HERE IS UP TO DATE
                         # IN SECTION 5.2 OF THE APIV2 "VERSIONING"
}


def run(ctx: protocol_api.ProtocolContext):

    [input_csv, source_type, dest_type] = get_values(  # noqa: F821
        'input_csv', 'source_type', 'dest_type')

    # define all custom variables above here with descriptions:
    left_pipette_loadname = 'p20_single_gen2'
    right_pipette_loadname = 'p300_single_gen2'

    target_plate_loader = (dest_type, '1',
                           'target plate')
    DNA_sample_plate_loader = (dest_type, '7',
                               'DNA sample plate')
    tiprack_300uL_loader = ('opentrons_96_filtertiprack_200ul', '2')
    tiprack_20uL_loader = ('opentrons_96_filtertiprack_20ul', '5')

    reservoir_loader = ('nest_12_reservoir_15ml', '4', 'water reservoir')

    # Initial 40 uL water for each well of the target
    initial_water_volume = 40

    # Read CSV and format the inputs
    # csv format: Well | Description | Concentration | volume to transfer
    #              [0]       [1]           [2]                [3]
    data = [
        [val.strip().upper() for val in line.split(',')
            if val != '']
        for line in input_csv.splitlines()[1:]
        if line and line.split(',')[0]]

    # Convert any well designation in column 1 from [A-H]0[1-9] to [A-H][1-9]
    # e.g. A01 -> A1 etc.
    pattern = re.compile('[A-H]0[1-9]')
    for row in data:
        if pattern.match(row[0]):
            row[0] = row[0].replace('0', '')

    # load modules

    '''

    Add your modules here with:

    module_name = ctx.load_module('{module_loadname}', '{slot number}')

    Note: if you are loading a thermocycler, you do not need to specify
    a slot number - thermocyclers will always occupy slots 7, 8, 10, and 11.

    For all other modules, you can load them on slots 1, 3, 4, 6, 7, 9, 10.

    '''

    # load labware
    '''

    Add your labware here with:

    labware_name = ctx.load_labware('{loadname}', '{slot number}')

    If loading labware on a module, you can load with:

    labware_name = module_name.load_labware('{loadname}')
    where module_name is defined above.

    '''
    reservoir = ctx.load_labware(reservoir_loader[0], reservoir_loader[1],
                                 reservoir_loader[2])
    dna_sample_plate = ctx.load_labware(DNA_sample_plate_loader[0],
                                        DNA_sample_plate_loader[1],
                                        DNA_sample_plate_loader[2])
    target_plate = ctx.load_labware(target_plate_loader[0],
                                    target_plate_loader[1],
                                    target_plate_loader[2])

    # load tipracks

    '''

    Add your tipracks here as a list:

    For a single tip rack:

    tiprack_name = [ctx.load_labware('{loadname}', '{slot number}')]

    For multiple tip racks of the same type:

    tiprack_name = [ctx.load_labware('{loadname}', 'slot')
                     for slot in ['1', '2', '3']]

    If two different tipracks are on the deck, use convention:
    tiprack[number of microliters]
    e.g. tiprack10, tiprack20, tiprack200, tiprack300, tiprack1000

    '''
    tiprack_20_filter = [ctx.load_labware(tiprack_20uL_loader[0],
                                          tiprack_20uL_loader[1])]
    tiprack_300_filter = [ctx.load_labware(tiprack_300uL_loader[0],
                                           tiprack_300uL_loader[1])]

    # load instrument

    '''
    Nomenclature for pipette:

    use 'p'  for single-channel, 'm' for multi-channel,
    followed by number of microliters.

    p20, p300, p1000 (single channel pipettes)
    m20, m300 (multi-channel pipettes)

    If loading pipette, load with:

    ctx.load_instrument(
                        '{pipette api load name}',
                        pipette_mount ("left", or "right"),
                        tip_racks=tiprack
                        )
    '''
    # Load m20 and p20, m20 switches out for p300 in step 2
    p20 = ctx.load_instrument(
                        left_pipette_loadname,
                        "left",
                        tip_racks=tiprack_20_filter
                        )
    p300 = ctx.load_instrument(
                        right_pipette_loadname,
                        "right",
                        tip_racks=tiprack_300_filter
                        )

    # pipette functions   # INCLUDE ANY BINDING TO CLASS

    '''

    Define all pipette functions, and class extensions here.
    These may include but are not limited to:

    - Custom pickup functions
    - Custom drop tip functions
    - Custom Tip tracking functions
    - Custom Trash tracking functions
    - Slow tip withdrawal

    For any functions in your protocol, describe the function as well as
    describe the parameters which are to be passed in as a docstring below
    the function (see below).

    def pick_up(pipette):
        """`pick_up()` will pause the protocol when all tip boxes are out of
        tips, prompting the user to replace all tip racks. Once tipracks are
        reset, the protocol will start picking up tips from the first tip
        box as defined in the slot order when assigning the labware definition
        for that tip box. `pick_up()` will track tips for both pipettes if
        applicable.

        :param pipette: The pipette desired to pick up tip
        as definited earlier in the protocol (e.g. p300, m20).
        """
        try:
            pipette.pick_up_tip()
        except protocol_api.labware.OutOfTipsError:
            ctx.pause("Replace empty tip racks")
            pipette.reset_tipracks()
            pipette.pick_up_tip()

    '''

    # helper functions
    '''
    Define any custom helper functions outside of the pipette scope here, using
    the convention seen above.

    e.g.

    def remove_supernatant(vol, index):
        """
        function description

        :param vol:

        :param index:
        """


    '''

    # reagents

    '''
    Define where all reagents are on the deck using the labware defined above.

    e.g.

    water = reservoir12.wells()[-1]
    waste = reservoir.wells()[0]
    samples = plate.rows()[0][0]
    dnase = tuberack.wells_by_name()['A4']

    '''
    water_well = reservoir.wells_by_name()['A1']
    liquid_waste = reservoir.wells_by_name()['A2']

    # plate, tube rack maps

    '''
    Define any plate or tube maps here.

    e.g.

    plate_wells_by_row = [well for row in plate.rows() for well in row]

    '''

    # protocol

    '''

    Include header sections as follows for each "section" of your protocol.

    Section can be defined as a step in a bench protocol.

    e.g.

    ctx.comment('\n\nMOVING MASTERMIX TO SAMPLES IN COLUMNS 1-6\n')

    for .... in ...:
        ...
        ...

    ctx.comment('\n\nRUNNING THERMOCYCLER PROFILE\n')

    ...
    ...
    ...


    '''

    ctx.comment("\nTransferring water to target plate\n")
    p300.pick_up_tip()
    for well in target_plate.wells():
        if p300.current_volume < initial_water_volume:
            p300.aspirate(200-p300.current_volume, water_well)
        p300.dispense(initial_water_volume, well)
    p300.blow_out(water_well)
    p300.return_tip()
    p300.reset_tipracks()

    # Transfering DNA samples to target
    ctx.comment("\nTransferring DNA sample to target plate\n")
    for line in data:
        well = line[0]
        description = line[1]
        concentration = line[2]
        volume = float(line[3])

        ctx.comment("Normalizing sample {} with concentration {}"
                    .format(description, concentration))
        pip = None
        pip = p20 if volume <= 20 else p300
        pip.pick_up_tip()
        pip.transfer(volume,
                     target_plate.wells_by_name()[well],
                     liquid_waste, new_tip="never")
        pip.transfer(volume,
                     dna_sample_plate.wells_by_name()[well],
                     target_plate.wells_by_name()[well], new_tip="never")
        pip.mix(3, 20)
        pip.blow_out(liquid_waste)
        pip.drop_tip()