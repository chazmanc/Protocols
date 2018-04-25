from opentrons import containers, instruments

p200rack = containers.load('tiprack-200ul', '10')
sample_tubes = containers.load('tube-rack-2ml', '11')
plate = containers.load('384-plate', '9')

p200 = instruments.P300_Single(
    mount="right",
    tip_racks=[p200rack],
)


def run_custom_protocol(number_of_tubes: int=24, transfer_volume: int=40):
    if number_of_tubes > len(sample_tubes):
        print(
            'Number of samples is too high: {}. The max is {}'.format(
                number_of_tubes, len(sample_tubes)))

    # dispense from tube to plate, for all tubes
    p200.transfer(
        transfer_volume,
        sample_tubes.wells('A1', length=number_of_tubes),
        plate.wells('A1', length=number_of_tubes),
        new_tips='always'
    )
