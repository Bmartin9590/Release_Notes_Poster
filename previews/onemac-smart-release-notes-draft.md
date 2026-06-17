# SMART Bi-Weekly Release to UAT

## At a Glance

- Top-level tickets: 141
- QA/support subtasks: 90
- Test Passed: 79
- Done: 62
- Bugs resolved: 35
- Stories delivered: 62

## Testing Metrics

System Integration Testing is shown sprint-wise for Sprint 2.1 through Sprint 2.4. Regression Testing in VAL covers the full Sprint 2.1 to Sprint 2.4 scope.

- **Sprint 2.1 - System Integration Testing** (R45447): 8 passed, 0 failed, 0 blocked, 0 retest, 0 untested out of 8 total.
- **Sprint 2.2 - System Integration Testing** (R45774): 13 passed, 0 failed, 0 blocked, 0 retest, 0 untested out of 13 total.
- **Sprint 2.3 - System Integration Testing** (R46093): 13 passed, 2 failed, 0 blocked, 0 retest, 0 untested out of 15 total.
- **Sprint 2.4 - System Integration Testing** (R46433): 19 passed, 2 failed, 1 blocked, 0 retest, 0 untested out of 22 total.
- **Sprint 2.1 to Sprint 2.4 - Regression Testing - VAL** (R43182): 29 passed, 1 failed, 0 blocked, 0 retest, 0 untested out of 30 total.
## Release Highlights

### Workflow, Review, and Status Improvements (38)

Enhancements and fixes across the SPA review workflow, RAI handling, SRT/CPOC decision points, status tracking, clocks, review pages, and related field behavior.

- **OMO-1055** [Bug / Test Passed] Remove Sub-status, Type, and Sub-Type from List Views & Dashboards/Reports _(Epic: No epic link)_
- **OMO-1322** [Bug / Test Passed] Status is changed to Pending Approval after one concurrer indicates 'Do Not Concur' _(Epic: No epic link)_
- **OMO-1353** [Bug / Test Passed] Label displayed as "Second Clock" when status moves from Second Clock to Pending RAI _(Epic: No epic link)_
- **OMO-1416** [Bug / Test Passed] SRT Assignment Notes page text label issue _(Epic: No epic link)_
- **OMO-1424** [Bug / Done] SPA Status is not moved to 'Approved' after Adjudicator approves _(Epic: No epic link)_
- **OMO-1426** [Bug / Test Passed] Consulting SME Questions are not included in Consolidated RAI Questions _(Epic: No epic link)_
- **OMO-593** [Bug / Test Passed] System allows to create RAI before all SRTs have completed review _(Epic: No epic link)_
- **OMO-927** [Bug / Test Passed] Error received when trying to assign CPOC as an SRT with no Assignment Notes _(Epic: No epic link)_
- **OMO-928** [Bug / Done] Unable to create RAI if CPOC user has indicated RAI Questions Completed as No during SRT Review _(Epic: No epic link)_
- **OMO-1078** [Story / Test Passed] Remove Request for Additional Information and Chatter from Right Sidebar _(Epic: OMO-634)_
- **OMO-1088** [Story / Done] Update RAI Fields _(Epic: OMO-634)_
- **OMO-1089** [Story / Test Passed] Standardize Submission ID Label to “ID” Across SMART _(Epic: OMO-634)_
- **OMO-755** [Story / Test Passed] Medicaid SPA: Exclude CPOC from Required SRT Fields and Mandatory Participation _(Epic: OMO-634)_
- **OMO-776** [Story / Test Passed] Remove “Time Since RAI Issued” After RAI Response Is Received _(Epic: OMO-634)_
- **OMO-787** [Story / Test Passed] Require CPOC on Initial Save of Submission Review Team Member _(Epic: OMO-634)_
- **OMO-901** [Story / Test Passed] Update Submission Types & Subtypes to Match CMS‑Provided List _(Epic: OMO-634)_
- **OMO-915** [Story / Test Passed] Update UI labels for Outstanding Items, 15th Day Call, and Reason for no 15th day call _(Epic: OMO-634)_
- **OMO-917** [Story / Test Passed] Remove Clarification Information section from Review Page and from SRT Detail Page _(Epic: OMO-634)_
- **OMO-1036** [Story / Test Passed] Update Label and Header from “Days on Active Clock” to “Days on Clock” _(Epic: OMO-666)_
- **OMO-1263** [Story / Test Passed] Update Field Label from “First Clock Review” to “First Clock Review Recommendation” _(Epic: OMO-666)_
- **OMO-785** [Story / Test Passed] Capture First Clock SRT Decision at RAI Issuance for Medicaid SPA _(Epic: OMO-666)_
- **OMO-1028** [Story / Test Passed] Medicaid SPA: Consolidate RAI Response Dates and Enable Full Field History Tracking _(Epic: OMO-669)_
- **OMO-1044** [Story / Test Passed] Support Consulting SME SRT Members With Required Participation _(Epic: OMO-669)_
- **OMO-1060** [Story / Test Passed] Add Group and Division to Contact Record in SMART _(Epic: OMO-669)_
- **OMO-1083** [Story / Test Passed] Update Progress Bar to Display Only Current Path with Dynamic Status Coloring _(Epic: OMO-669)_
- **OMO-1090** [Story / Test Passed] Require CPOCs to Meet SRT Review and RAI Decision Standards on SRT Detail Page _(Epic: OMO-669)_
- **OMO-1091** [Story / Test Passed] Remove Status Field from RAI Detail Page _(Epic: OMO-669)_
- **OMO-1162** [Story / Test Passed] Progress Bar and Status: Default Status to “Intake Needed” and Progress Bar reflects First Clock and the correct status _(Epic: OMO-669)_
- **OMO-1266** [Story / Test Passed] Update Label from “Consultant/SME” to “Consulting SME” _(Epic: OMO-669)_
- **OMO-781** [Story / Test Passed] Make Priority Code Field Optional _(Epic: OMO-669)_
- **OMO-887** [Story / Test Passed] Document and Track RAI status for Medicaid SPA _(Epic: OMO-669)_
- **OMO-1006** [Task / Test Passed] Spike: Technical Evaluation of Notes Custom Component in SMART _(Epic: OMO-669)_
- **OMO-1265** [Task / Done] Create Email Alert Templates for Withdrawn and Return to Review Team Statuses _(Epic: OMO-669)_
- **OMO-989** [Task / Done] SPIKE: Track Field-Level Changes in SMART _(Epic: OMO-669)_
- **OMO-815** [Story / Test Passed] Concurrer should be able to Concur to Approve Medicaid SPA _(Epic: OMO-670)_
- **OMO-954** [Story / Test Passed] Require “Submission Verified Complete” Before RAI, Concurrence, or Approval _(Epic: OMO-670)_
- **OMO-788** [Task / Done] SPIKE: Support Alternate CPOC for Submission Coverage _(Epic: OMO-670)_
- **OMO-889** [Story / Test Passed] Enforce Submission ID Format, Uniqueness, and State Alignment _(Epic: OMO-671)_

### Data Migration and Record Quality (34)

SEA Tool migration and data quality work covering loaded records, duplicate SPA IDs, field mappings, status/date values, formatting, and record completeness.

- **OMO-1008** [Bug / Test Passed] Outstanding Issues _(Epic: OMO-1122)_
- **OMO-1034** [Bug / Test Passed] Component ID with Additional Reviewing Division is missing State Plan data _(Epic: OMO-1122)_
- **OMO-1051** [Bug / Done] Camel casing issue in the displayed message_SubType _(Epic: OMO-1122)_
- **OMO-1159** [Bug / Done] Status date is not displayed for different statuses for the SPA _(Epic: OMO-1122)_
- **OMO-1167** [Bug / Test Passed] CPOC and SRT data not loaded for the SPAs in SMART Application _(Epic: OMO-1122)_
- **OMO-1169** [Bug / Test Passed] Order of the files uploaded in OneMAC are not same in SMART _(Epic: OMO-1122)_
- **OMO-1184** [Bug / Test Passed] SPA Status not updated correctly after CPOC (only one assigned for review) recommends approval _(Epic: OMO-1122)_
- **OMO-1269** [Bug / Test Passed] RAI Status is displayed as RAI Under developement for the SPA IDs loaded in SMART _(Epic: OMO-1122)_
- **OMO-1291** [Bug / Test Passed] SEA Tool's SPA/Waiver name is different from SMART's SPA/Waiver Name _(Epic: OMO-1122)_
- **OMO-1294** [Bug / Test Passed] SMART's Imact Year Values displayed without comma separator _(Epic: OMO-1122)_
- **OMO-1296** [Bug / Test Passed] RAI Response Greater Than 90 days checkbox issue _(Epic: OMO-1122)_
- **OMO-525** [Bug / Test Passed] Active Records Loaded in Sprint 1.1_Second Clock Start Date Issues _(Epic: OMO-1122)_
- **OMO-544** [Bug / Test Passed] Second Clock Start Date not populated for the SPAs with Approved Status _(Epic: OMO-1122)_
- **OMO-645** [Bug / Test Passed] Data Migration_UI fields validation_Missing Status field value _(Epic: OMO-1122)_
- **OMO-796** [Bug / Test Passed] Issues under Attachments tab. _(Epic: OMO-1122)_
- **OMO-968** [Bug / Test Passed] Data truncated for SMART_CMCS_Subject__c from source to target _(Epic: OMO-1122)_
- **OMO-969** [Bug / Done] 33 SPA IDs not loaded into SMART application due to issue with Initial Submission Date _(Epic: OMO-1122)_
- **OMO-970** [Bug / Test Passed] State Early Alerts data issues _(Epic: OMO-1122)_
- **OMO-974** [Bug / Test Passed] Multiple SPA IDs with none as value for SMART_CMCS_Priority_Code__c is mapped to P3 - Expedited Review _(Epic: OMO-1122)_
- **OMO-981** [Bug / Done] Discrepancy in 90th_Day values from SEA tool to SMART _(Epic: OMO-1122)_
- **OMO-995** [Bug / Test Passed] RAI Data not loaded for SPA IDs with duplicates in SMART _(Epic: OMO-1122)_
- **OMO-996** [Bug / Test Passed] SRT Data not loaded for SPA IDs with duplicates in SMART _(Epic: OMO-1122)_
- **OMO-997** [Bug / Test Passed] CPOC Data not loaded for SPA IDs with duplicates in SMART _(Epic: OMO-1122)_
- **OMO-1308** [Task / Done] Record Type to QA _(Epic: OMO-650)_
- **OMO-921** [Task / Done] OneMAC DM 2_1_Data_Mapping - SP2.1 _(Epic: OMO-650)_
- **OMO-1001** [Story / Done] SEA Tool Data Migration to SMART for SPA & Waivers - ETL/Load - 2.2 - Cycle 2 QA _(Epic: OMO-654)_
- **OMO-919** [Story / Test Passed] SEA Tool Data Migration to SMART for Medicaid SPA - ETL/Load - 2.1 _(Epic: OMO-654)_
- **OMO-1000** [Task / Done] SEA Tool DM 2_1_Data_Mapping - SP2.2 - Cycle 2 _(Epic: OMO-654)_
- **OMO-1058** [Task / Done] Push the permission sets to QA _(Epic: OMO-654)_
- **OMO-918** [Task / Done] SEA Tool DM 2_1_Data_Mapping - SP2.1 _(Epic: OMO-654)_
- **OMO-342** [Story / Test Passed] Adjudicated - QA SEA Tool DM 4_1_Record-by-Record and Attribute-by-Attribute validation _(Epic: OMO-748)_
- **OMO-904** [Story / Test Passed] SEA Tool Data Migration to SMART for records in MVP scope - Medicaid SPA _(Epic: OMO-748)_
- **OMO-957** [Task / Done] SEA Tool DM for Medicaid SPA - Pushing Fields to QA _(Epic: OMO-748)_
- **OMO-964** [Task / Done] SEA Tool DM for Medicaid SPA - Pushing Fields to QA pt 2 _(Epic: OMO-748)_

### OneMAC Integration and Attachments (15)

Integration readiness and event-driven work between OneMAC and SMART, including MSP lifecycle events, attachment metadata, downloadable documents, and lower-environment validation.

- **OMO-1123** [Bug / Test Passed] Unable to downlaod the documents using downloadable buttons and section override issue _(Epic: OMO-655)_
- **OMO-767** [Story / Test Passed] Update SMART Record Attachments Tab - Some additional updates _(Epic: OMO-655)_
- **OMO-833** [Story / Test Passed] MSP Record Creation & Initial Status Assignment for MSP Initial Submission Event _(Epic: OMO-655)_
- **OMO-834** [Story / Test Passed] Attachment Metadata Handling & S3 Link Generation (Initial MSP Submission) _(Epic: OMO-655)_
- **OMO-837** [Story / Test Passed] Spike - Outbound Event Definition (MSP Lifecycle) _(Epic: OMO-655)_
- **OMO-838** [Story / Test Passed] Medicaid SPA Record Updates for All State Generated Events originating in OneMAC _(Epic: OMO-655)_
- **OMO-839** [Story / Done] Complete Status Transition Logic and Other Fields based on Event _(Epic: OMO-655)_
- **OMO-977** [Story / Test Passed] Preserve Attachment Order from OneMAC _(Epic: OMO-655)_
- **OMO-992** [Story / Done] Test all the Inbound Events using VPN/VPC connectivity _(Epic: OMO-655)_
- **OMO-1003** [Story / Done] UAT Environment Integration Readiness _(Epic: OMO-656)_
- **OMO-598** [Story / Test Passed] Spike: Validate SMART OOTB Support for Event Envelope Capabilities and Document event envelope _(Epic: OMO-656)_
- **OMO-818** [Story / Test Passed] "Initial MSP Submission" Event Integration Validation (Mock-Based) _(Epic: OMO-656)_
- **OMO-821** [Story / Test Passed] Integration Logging Enablement _(Epic: OMO-656)_
- **OMO-822** [Story / Test Passed] Lower Environment Integration Readiness _(Epic: OMO-656)_
- **OMO-752** [Task / Done] Prep - OneMAC SMART to Prod _(Epic: OMO-747)_

### Roles, Permissions, and Access (11)

SMART role creation and access behavior for Adjudicator, Concurrer, Intake, SRT, CPOC, CMS users, SuperUsers, and restricted identifying information.

- **OMO-269** [Story / Test Passed] Create Intake Role in SMART _(Epic: OMO-652)_
- **OMO-270** [Story / Test Passed] Create SRT Role in SMART _(Epic: OMO-652)_
- **OMO-271** [Story / Test Passed] Create Adjudicator Role in SMART _(Epic: OMO-652)_
- **OMO-272** [Story / Test Passed] Create Concurrer Role in SMART _(Epic: OMO-652)_
- **OMO-273** [Story / Test Passed] Create General CMS User (Read Only) Role in SMART _(Epic: OMO-652)_
- **OMO-275** [Story / Test Passed] Create CPOC Role in SMART _(Epic: OMO-652)_
- **OMO-553** [Story / Test Passed] Restrict visibility of Identifying Information to SuperUsers only for Medicaid SPA _(Epic: OMO-652)_
- **OMO-749** [Story / Test Passed] Create SuperUser Role in SMART _(Epic: OMO-652)_
- **OMO-750** [Story / Test Passed] Create CMS General User Role in SMART _(Epic: OMO-652)_
- **OMO-816** [Story / Test Passed] Adjudicator Role – Approve or Disapprove Medicaid SPA Submissions _(Epic: OMO-670)_
- **OMO-817** [Story / Test Passed] SRT Member Role – Recommend Approval/Disapproval for Medicaid SPA Submissions _(Epic: OMO-670)_

### Design, Research, and Content Readiness (35)

HCD, research, UX content, discovery, feedback collection, design decisions, and future-facing product readiness work.

- **OMO-1418** [Task / Done] Epic Approval Mural _(Epic: No epic link)_
- **OMO-1042** [Story / Done] HCD | Define pod norms for roles, responsibilities, and meeting ownership _(Epic: OMO-581)_
- **OMO-1155** [Story / Done] Review SMART MVP materials _(Epic: OMO-581)_
- **OMO-1004** [Task / Done] HCD Designs - Concurrer should be able to Concur to Approve Medicaid SPA _(Epic: OMO-581)_
- **OMO-1005** [Task / Done] HCD Designs - Adjudicator should be able to Adjudicate to Approve Medicaid SPA _(Epic: OMO-581)_
- **OMO-1031** [Task / Done] HCD Companion Letter (Tracking) UI Mockup _(Epic: OMO-581)_
- **OMO-1134** [Task / Done] Review SMART MVP materials _(Epic: OMO-581)_
- **OMO-1298** [Task / Done] Create design decision records _(Epic: OMO-581)_
- **OMO-1303** [Task / Done] Create Qualtrics feedback form for OneMAC and MACPro usability testing _(Epic: OMO-581)_
- **OMO-1315** [Task / Done] Start early designs for waiver temporary extensions _(Epic: OMO-581)_
- **OMO-697** [Task / Done] R&D | Generating letters (companion letter) prep continued _(Epic: OMO-581)_
- **OMO-911** [Task / Done] SMART Alert Emails - UX Content continuation _(Epic: OMO-581)_
- **OMO-912** [Task / Done] Synthesize CHIP meeting notes (4/23) _(Epic: OMO-581)_
- **OMO-922** [Task / Done] Onboarding Samiyah _(Epic: OMO-581)_
- **OMO-951** [Task / Done] Error Message for Attachments Tab _(Epic: OMO-581)_
- **OMO-956** [Task / Done] Prep for Dovetail to OneDrive transition _(Epic: OMO-581)_
- **OMO-960** [Task / Done] Synthesize 1915(c) - Meeting 2 (4/21) _(Epic: OMO-581)_
- **OMO-961** [Task / Done] Synthesize Small Group Discussion Meeting - 4/22 _(Epic: OMO-581)_
- **OMO-962** [Task / Done] Synthesize 1915(b) - Meeting 3 (4/22) _(Epic: OMO-581)_
- **OMO-963** [Task / Done] Synthesize 1915(c) - Meeting 3 (4/22) _(Epic: OMO-581)_
- **OMO-976** [Task / Done] Helper Text: review and edit 1915(c) fields _(Epic: OMO-581)_
- **OMO-978** [Task / Done] Create design for “Enable Formal RAI Response Withdraw” button in SMART _(Epic: OMO-581)_
- **OMO-998** [Task / Done] Alert Emails: Reviewing feedback and making edits continuation _(Epic: OMO-581)_
- **OMO-820** [Story / Test Passed] Design Spike - Error Handling & Integration Handshake _(Epic: OMO-656)_
- **OMO-1262** [Task / Done] Small Group Design: Companion Letter Tracking Iterations _(Epic: OMO-669)_
- **OMO-1279** [Task / Done] SMC Confirm Designs: 1st Clock Memorialized on Review tab _(Epic: OMO-669)_
- **OMO-1417** [Task / Done] Small Group Companion Letter Tracking Design Confirmation _(Epic: OMO-669)_
- **OMO-1039** [Story / Done] RUs | Prepare for small group session _(Epic: OMO-806)_
- **OMO-1040** [Story / Done] RUs| Draft and refine RU workflow for State Users _(Epic: OMO-806)_
- **OMO-1041** [Story / Done] RUs | Explore custom component process _(Epic: OMO-806)_
- **OMO-1052** [Task / Done] RUs | Former state user research write up for Maria _(Epic: OMO-806)_
- **OMO-923** [Task / Done] RUs | Brainstorm design session _(Epic: OMO-806)_
- **OMO-924** [Task / Done] RUs | Elevator pitch for state user research _(Epic: OMO-806)_
- **OMO-925** [Task / Done] RUs | Prep research questions for state users _(Epic: OMO-806)_
- **OMO-987** [Task / Done] RUs | Explore custom component process _(Epic: OMO-806)_

### Release Readiness and Operations (6)

Operational work supporting QA, production readiness, Copado movement, SharePoint/process documentation, and environment preparation.

- **OMO-907** [Bug / Test Passed] Home Page (Dashboards and Reports) , Unassigned SPAs - show ID Number deprecated field _(Epic: No epic link)_
- **OMO-1038** [Story / Test Passed] Create Test Users in QA _(Epic: No epic link)_
- **OMO-1422** [Story / Done] Update Impact Year 1 and Impact Year 2 Fields to Currency Format _(Epic: No epic link)_
- **OMO-751** [Task / Done] Sharepoint workflow documentation _(Epic: OMO-677)_
- **OMO-739** [Story / Done] prep for Copado pipeline changes (Apr 29-30 Migrating Pipeline) _(Epic: OMO-747)_
- **OMO-1065** [Task / Done] Copado Deployment to QA _(Epic: OMO-747)_

### Other Product Maintenance (2)

Standalone cleanup or maintenance items that did not map cleanly to a larger functional theme from the CSV fields.

- **OMO-741** [Bug / Done] ID Number is not marked as a mandatory field _(Epic: No epic link)_
- **OMO-1304** [Task / Done] Load type/sub-type data _(Epic: No epic link)_
