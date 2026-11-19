# Things to know

Decisions, limits and behaviours that a university buying Anveshan, its administrators and
anyone writing the SRS or user manuals must know. Each point says what happens, why, and where
it was decided. Add to this file whenever a change leaves something a user could not guess;
remove a point only when the behaviour itself changes.

## The PhD file (PRD F17)

1. **Each person gets their own copy of the file.** Every annexure follows the same visibility
   rules as its screen, so two roles downloading the same scholar's file can get different
   contents. A part the caller may not read is listed as "Not shown to you"; a part whose
   module the university has switched off, as "Not in use at this university"; an empty part,
   as "Not on record". For example, the Research Office does not see the copies of the
   synopsis and proposal, because it cannot open the scholar's documents on screen either.
   *(2026-11-19)*
2. **The index uses Anveshan's 16 headings for now**, not the university's own numbered list
   (Medi-Caps keeps 30 rows with its own form numbers: II-B, IV, V, VI, VII-A …). The
   university's own titles, form numbers and "copy to" lists will become settings in a later
   part. *(2026-11-19)*
3. **The pages after the index are summaries for now.** They print stored values as they are
   (for example "approved", "minor revision"). Proper forms laid out like the university's
   paper forms come next. *(2026-11-19)*
4. **"Corrections made for the examiners" has no record of its own.** It is held as an
   uploaded paper on the thesis submission ("Modifications made at the examiners' request").
   *(2026-11-19)*

## Signed or unsigned downloads (PRD F17b)

5. **A form that carries signatures asks "Download signed or unsigned?"** Signed prints the
   signatures on record. Unsigned leaves them out and gives a signature and date line for each
   signatory, so the printed copy can be signed by hand and its scan uploaded. *(owner,
   2026-11-19)*
6. **Today only the progress report offers the choice.** Its unsigned copy has lines for the
   scholar and each advisory committee member, or for the supervisor when no committee is
   recorded. The PhD file gets the same choice when its forms are built. *(2026-11-19)*

## Signed papers for the PhD file (PRD F17b)

7. **Who uploads and who approves.** The scholar's supervisor, the department admin or the
   Research Office uploads the scan of a paper signed by hand. The department admin's and the
   Research Office's uploads count at once. A supervisor's upload waits until the department
   admin or the Research Office approves it, and they are notified. The scholar cannot upload
   or approve. Every upload, approval and removal is in the audit log. *(owner, 2026-11-19)*
8. **Every paper of the university's file has a place.** Each seminar holds its notification,
   report and attendance sheet. Each committee decision holds the DRC minutes and the notice of
   the DRC chairperson. The thesis submission holds its signed form, the examination fee due
   creation and the modifications made at the examiners' request. The viva arrangement holds
   its approval, the constitution of the examination board, the notification and the email to
   the viva examiner. The viva holds its report and attendance sheet. Every other entry holds
   one signed copy. *(owner, 2026-11-19)*
9. **The examiners' papers are kept apart.** The panel of examiners and the emails to and
   acceptances from the national and international examiners sit on their own entry. Only the
   Research Office, the Exam Office and the department admin see, upload and approve them, and
   their uploads count at once. The scholar never sees them, and neither does the supervisor
   or co-supervisor, even one who also holds one of those roles. *(owner, option a,
   2026-11-19)*
10. **The department admin sees examiner names in those papers before the viva.** On the
    screens, the department does not see examiner names until the viva. This difference is
    deliberate for now; it can be narrowed to the Research Office and the Exam Office only.
    *(2026-11-19)*
11. **One file per paper.** When there are two national examiners, both letters go in as one
    PDF. Uploading again replaces the copy in use; the old one stays on record.
    *(2026-11-19)*
12. **Only PDF, PNG or JPEG.** The scans go into the PhD file as pages, so Word and other
    files are refused. A scan that cannot be read (locked, damaged, a blank page) leaves a note
    in the file instead of breaking it. *(2026-11-19)*
13. **An approved paper marks its entry "Signed" in the index**, and its pages follow the
    entry in the downloaded file, in the order listed in point 8. *(2026-11-19)*
14. **Anveshan does not send the emails to examiners.** It keeps the uploaded copies of the
    emails and acceptances the office sent and received outside the portal. *(2026-11-19)*

## Setting up a real installation

15. **Two-factor sign-in and signing approvals are off by default.** They are off for the
    demo. The owner wants both switched on at every real university installation (Settings).
    *(owner)*
16. **The university types in its own seminar marking questions.** The Form VII / VIII
    questions used to mark registration and synopsis seminars are entered in Settings; the
    demo ships with sample questions. *(owner)*
17. **Specimen signatures are confirmed by someone else.** A person's own upload waits until
    an admin over their unit or the Research Office confirms it; unit heads cannot confirm.
    *(2026-11-18)*
