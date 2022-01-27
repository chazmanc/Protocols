# Fetal DNA NGS library preparation part 2 - LifeCell NIPT 35Plex HV - Barcoding

### Author
[Opentrons](https://opentrons.com/)

## Categories
* NGS Library Prep

## Description
This protocol mixes end-repaired DNA samples with adaptor ligation mastermix and DNA barcodes specified according to a CSV input file

* `Number of samples`: The number of DNA samples on your sample plate. Should be between 7 and 36.

Explanation of complex parameters below:
* `Sample:Barcode Input CSV File`: Upload a CSV file with the formatting shown in the block below that specifies which sample is mixed with which barcode and the barcode's identifier:

**Example**
```
DNA_sample_well,barcode_number, Adapter,Sample_ID,plate_number
A1,1,pmh001a,s1,adapt.01
B1,2,pmh002a,s2,adapt.02
C1,3,pmh003a,s3,adapt.03
```

Please make sure that there is enough volume of all the barcodes you intend to use before running this protocol.

---

### Labware
* [Bio-Rad 96 well 200 µL PCR plate](https://labware.opentrons.com/biorad_96_wellplate_200ul_pcr?category=wellPlate)
* [NEST 12-well reservoir](https://labware.opentrons.com/nest_12_reservoir_15ml/)

### Pipettes
* [P300 Single Channel GEN2](https://shop.opentrons.com/single-channel-electronic-pipette-p20/)
* [P20 Single Channel GEN2](https://shop.opentrons.com/single-channel-electronic-pipette-p20/)
* [Opentrons 96 Filter Tip Rack 20 µL](https://labware.opentrons.com/opentrons_96_filtertiprack_20ul/)
* [Opentrons 96 Filter Tip Rack 200 µL](https://labware.opentrons.com/opentrons_96_filtertiprack_200ul/)

---

### Deck Setup

![deck layout](https://opentrons-protocol-library-website.s3.amazonaws.com/custom-README-images/466f93/deck_state_part2_466f93.jpeg)

![reservoir layout](https://opentrons-protocol-library-website.s3.amazonaws.com/custom-README-images/466f93/reservoir_layout_466f93_part4.jpeg)

### Reagent Setup
* Slot 1 Plate with end-repaired samples (from part 1)
* Slot 3 Empty
* Slot 4 Destination Plate 2
* Slot 5 200 µL Opentrons filter tips
* Slot 6 12-well reservoir Well 2: Nuclease free water (5-10 mL is plenty)
* Slot 7 Yourgene cfDNA Library Prep Kit Library Preparation Plate I
* Slot 8 200 µL Opentrons filter tips
* Slot 9 Empty
* Slot 10 20 µL Opentrons filter tips
* Slot 11 20 µL Opentrons filter tips

---

### Protocol Steps
1. The user places all the required labware on the deck and makes sure to replace any used or partially used tip racks
2. The protocol starts by creating a mastermix of Adaptor ligation buffer, enzyme I and enzyme II, and water in well B5 and C5 of the Yourgene reagent plate I and mixes it 10 times
3. The mastermix is transferred to Destination Plate 2 (8 µL per sample)
4. End-repaired DNA sample from the End-repaired sample plate on Slot 1 (i.e. Destination Plate 1) is transferred to Destination Plate 2 (DP-2)
5. Barcode oligos are transferred to each well according to the input csv (2 µL per sample)
6. Finally the samples on DP-2 are mixed ten times
7. The user is asked to pulse spin the plate and perform the incubation step.

### Process
1. Input your protocol parameters above.
2. Download your protocol and unzip if needed.
3. Upload your protocol file (.py extension) to the [OT App](https://opentrons.com/ot-app) in the `Protocol` tab.
4. Set up your deck according to the deck map.
5. Calibrate your labware, tiprack and pipette using the OT App. For calibration tips, check out our [support articles](https://support.opentrons.com/en/collections/1559720-guide-for-getting-started-with-the-ot-2).
6. Hit 'Run'.

### Additional Notes
If you have any questions about this protocol, please contact the Protocol Development Team by filling out the [Troubleshooting Survey](https://protocol-troubleshooting.paperform.co/).

###### Internal
466f93-2