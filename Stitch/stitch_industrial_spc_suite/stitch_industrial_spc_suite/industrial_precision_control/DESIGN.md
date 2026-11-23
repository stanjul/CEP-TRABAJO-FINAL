---
name: Industrial Precision Control
colors:
  surface: '#f8f9ff'
  surface-dim: '#cbdbf5'
  surface-bright: '#f8f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#eff4ff'
  surface-container: '#e5eeff'
  surface-container-high: '#dce9ff'
  surface-container-highest: '#d3e4fe'
  on-surface: '#0b1c30'
  on-surface-variant: '#40484b'
  inverse-surface: '#213145'
  inverse-on-surface: '#eaf1ff'
  outline: '#70787c'
  outline-variant: '#c0c8cb'
  surface-tint: '#306576'
  primary: '#003441'
  on-primary: '#ffffff'
  primary-container: '#0f4c5c'
  on-primary-container: '#87bbce'
  inverse-primary: '#9acee1'
  secondary: '#086a5f'
  on-secondary: '#ffffff'
  secondary-container: '#a1f2e2'
  on-secondary-container: '#167164'
  tertiary: '#032879'
  on-tertiary: '#ffffff'
  tertiary-container: '#254090'
  on-tertiary-container: '#9bb0ff'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#b6ebfe'
  primary-fixed-dim: '#9acee1'
  on-primary-fixed: '#001f28'
  on-primary-fixed-variant: '#114d5d'
  secondary-fixed: '#a1f2e2'
  secondary-fixed-dim: '#85d5c6'
  on-secondary-fixed: '#00201c'
  on-secondary-fixed-variant: '#005047'
  tertiary-fixed: '#dce1ff'
  tertiary-fixed-dim: '#b6c4ff'
  on-tertiary-fixed: '#00164e'
  on-tertiary-fixed-variant: '#264191'
  background: '#f8f9ff'
  on-background: '#0b1c30'
  surface-variant: '#d3e4fe'
typography:
  headline-xl:
    fontFamily: Inter
    fontSize: 40px
    fontWeight: '700'
    lineHeight: 48px
    letterSpacing: -0.02em
  headline-xl-mobile:
    fontFamily: Inter
    fontSize: 28px
    fontWeight: '700'
    lineHeight: 36px
    letterSpacing: -0.01em
  headline-lg:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
    letterSpacing: -0.01em
  headline-lg-mobile:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '700'
    lineHeight: 32px
  headline-md:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  headline-sm:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
  label-lg:
    fontFamily: JetBrains Mono
    fontSize: 16px
    fontWeight: '600'
    lineHeight: 22px
    letterSpacing: 0.02em
  label-md:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '500'
    lineHeight: 18px
    letterSpacing: 0.01em
  label-sm:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '500'
    lineHeight: 14px
    letterSpacing: 0.04em
  metric-display:
    fontFamily: JetBrains Mono
    fontSize: 36px
    fontWeight: '700'
    lineHeight: 40px
    letterSpacing: -0.03em
  metric-display-mobile:
    fontFamily: JetBrains Mono
    fontSize: 26px
    fontWeight: '700'
    lineHeight: 32px
    letterSpacing: -0.02em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  gutter: 1rem
  gutter-desktop: 1.5rem
  margin: 1rem
  margin-desktop: 2rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 0.75rem
  space-lg: 1.25rem
  space-xl: 2rem
---

## Brand & Style

This design system delivers rugged, mission-critical operational clarity for factory shopfloor touch terminals, manufacturing workstation monitors, and quality engineering analytical suites. The target audience comprises machine operators, shift supervisors, metrologists, and quality control engineers navigating complex Statistical Process Control (SPC / CEP) workflows in demanding, high-glare plant environments.

The visual style blends **Technical Minimalism** with **Tactile Industrial Precision**:
- High-contrast, glare-resilient structural planes engineered for distance legibility and grease/glove-compatible touch interfaces.
- Zero decorative fluff: visual weight is strictly calibrated to represent statistical significance, control limits, and operational risk.
- Structural stability inspired by physical machinery displays, mechanical instrumentation panels, and calibrated measurement readouts.
- High emotional reliability: operators experience immediate spatial orientation, absolute certainty regarding machine states, and zero visual ambiguity during out-of-spec incidents.

## Colors

The palette establishes an unambiguous hierarchy between operational structure, user interaction, and process alerts.

### Structural & Core Brand Colors
- **Canvas Background**: Deep off-white and cool gray layers (`#F3F4F6`, `#F8FAFC`) to minimize eye fatigue under harsh industrial LED lighting while avoiding panel glare.
- **Card & Surface Background**: Solid crisp white (`#FFFFFF`) to ground analytical instrumentation and interactive components.
- **Structural Outlines & Grids**: Technical slate borders (`#CBD5E1` default, `#94A3B8` active/dividers) providing high structural legibility without visual noise.
- **Primary Accent (`#0F4C5C`)**: Deep petroleum blue, reserved strictly for navigation anchors, primary system actions, structural headers, and focused inputs.
- **Secondary Accent (`#136F63`)**: Petrol teal, deployed for secondary tool triggers, active filter pills, and neutral telemetry indicators.
- **Tertiary Accent (`#1E3A8A`)**: Deep technical blue, dedicated to statistical baseline overlays, nominal median lines (LC), and reference specs (Cp/Cpk target bands).

### Semantic Traffic Light Rule (Strict Isolation)
Green, amber, and red are strictly quarantined from UI decoration, brand identity, or general success states. They represent real-time physical machine telemetry and control limits:
- **Under Control / Normal**: Deep forest green (`#15803D`) on soft mint tint (`#DCFCE7`). Indicates stable Cpk, in-control runs, and verified batches.
- **Warning / Nelson Rules Trigger**: Dense amber (`#B45309`) on pale amber tint (`#FEF3C7`). Signals approaching control limits (LES/LEI), trending runs, or drift.
- **Out of Control / Alarm**: Vivid industrial red (`#B91C1C`) on light crimson tint (`#FEE2E2`). Flags critical threshold breaches (LCS/LCI violations), scrap hazards, and emergency line-stops.

## Typography

Typography prioritizes rapid scanning, tabular alignment, and zero ambiguity between numerals.

- **Primary Interface Font (Inter)**: Handles descriptive UI text, standard interaction elements, column headers, and administrative dialogues. Tabular figures (`tnum`) must be enabled by default across all styles.
- **Monospace Telemetry Font (JetBrains Mono)**: Handles all statistical readouts, limits (LCS, LC, LCI, LES, LEI), indices ($C_p, C_{pk}, P_p, P_{pk}$), sample sizes ($N$), and parts-per-million ($ppm$) counts. It provides fixed-width structural alignment across dense data grids and live chart legends.
- **Hierarchy & Visual Weight**: Key performance figures use `metric-display` with distinct unit sub-labels. Micro-labels for technical parameters (`label-sm`) default to uppercase with tracking to preserve scanability on low-dpi shopfloor displays.

## Layout & Spacing

The layout philosophy centers on a deterministic, high-density fluid grid engineered to scale between ruggedized 10-inch shopfloor touchscreen panels and multi-window 27-inch quality engineering monitors.

### Layout Philosophy
- **Shopfloor Workstations (Touch Mode)**: Large targets with a condensed outer margin (`margin: 1rem`) to maximize the live chart footprint, featuring touch-optimized target minimums of 48px height for all control inputs.
- **Engineering Desktop (High Density)**: A 12-column layout with 24px gutters (`gutter-desktop`) structured for concurrent Shewhart control charts ($\bar{X}-R$, $\bar{X}-S$), histograms with Gaussian bell overlays, and live inspection run tables.
- **Rhythm & Gaps**: Compact component spacing (`space-sm` for card inner widgets, `space-md` between parameter modules) maintains tight visual grouping, eliminating scanning gaps between statistical metrics and real-time alerts.

## Elevation & Depth

To prevent wash-out under harsh ambient lighting and ensure immediate structural contrast, this system rejects soft decorative blur effects and heavy drop-shadows in favor of **Tonal Layering with Crisp Technical Outlines**:

- **Ground Level (Base Canvas)**: Neutral technical field (`#F3F4F6` or `#F8FAFC`).
- **Surface Level 1 (Inspection Cards & Modules)**: Flat `#FFFFFF` bound by a solid 1px border of `#CBD5E1`.
- **Surface Level 2 (Active Toolbars, Selected Rows, Sub-Panels)**: Elevated via crisp 1px borders of `#94A3B8` and a subtle 2px downward tactile shadow (`0 2px 0 0 rgba(15, 23, 42, 0.08)`).
- **Alarm / Hazard Overlays**: Elevated out-of-control floating warnings utilize high-contrast borders (2px solid `#B91C1C`) combined with an ambient high-opacity, zero-blur perimeter offset (`0 4px 12px 0 rgba(185, 28, 28, 0.20)`).
- **Control Chart Depth**: Charts employ faint horizontal grid lines (`#E2E8F0`, 1px dashed) with solid reference boundary baselines for LCS/LCI (`#B91C1C`) and LC (`#1E3A8A`).

## Shapes

The shape system adopts a **Soft / Precision Engineered** geometry (`roundedness: 1`). Corners maintain an exact 0.25rem (4px) radius for basic controls and inputs, 0.5rem (8px) for analytical containers and cards, and 0.75rem (12px) for high-level modal dialogs. 

Fully circular pills are avoided except for status notification badges and active filter tags. The geometric rigidity reinforces a machined, calibrated instrument aesthetic suitable for mission-critical industrial hardware.

## Components

### Buttons
- **Touch-Action Buttons (Shopfloor)**: Minimum height of 48px. Solid background (`#0F4C5C` for primary, `#FFFFFF` with 1.5px `#CBD5E1` border for secondary), high-contrast white or deep petroleum typography, and an active state with 1px inset depression to mimic physical hardware buttons.
- **Emergency / Line Hold Triggers**: Dedicated high-visibility red surface (`#B91C1C`), uppercase bold typography, reinforced with a 2px outer gap border.

### Telemetry Cards & Metric Blocks
- Structured containers with a crisp 1px border (`#CBD5E1`) and solid `#FFFFFF` fill.
- Top section holds parameter names in `label-sm` (slate `#64748B`), centered value displays the latest reading in `metric-display`, and bottom baseline details tolerance boundaries (LCS / LCI) alongside current $C_{pk}$ values.
- Card state shifts automatically to tinted backgrounds upon alarm triggers (`#FEF3C7` warning, `#FEE2E2` critical).

### Statistical Process Control (SPC) Charts
- Fixed aspect-ratio canvas embedded directly into white cards.
- **Center Line (LC)**: Solid 1.5px `#1E3A8A` stroke.
- **Upper / Lower Control Limits (LCS / LCI)**: 1.5px dash-dotted `#B91C1C` lines.
- **Upper / Lower Specification Limits (LES / LEI)**: 1px dotted `#B45309` lines.
- **Data Points**: Monospace data callouts with 6px circular nodes. Points violating Nelson rules turn solid red with an animated 2px beacon ring.

### Data Tables (High Density)
- Alternating row zebra-striping (`#FFFFFF` to `#F8FAFC`).
- Compact padding (`0.5rem 0.75rem`) per cell.
- All numbers align right using `JetBrains Mono` tabular figures; text descriptions align left in `Inter`.
- Strict out-of-control row highlighting using semantic cell tags rather than full-row flooding.

### Status Chips & Pills
- Compact, 20px-height badges with 2px corner radius.
- Under Control: `#DCFCE7` background, `#15803D` border and text.
- Warning: `#FEF3C7` background, `#B45309` border and text.
- Out of Control: `#FEE2E2` background, `#B91C1C` border and text.

### Form Inputs & Limit Threshold Sliders
- Strict 40px/48px height with 1px border (`#CBD5E1`), darkening to `#0F4C5C` on focus with 2px offset.
- Number inputs default to monospace font with built-in increment stepper controls scaled for stylus or gloved interaction.