/**
 * lib/diseases.ts
 * ───────────────
 * Disease knowledge base + label resolver.
 *
 * Ported verbatim from the legacy `static/js/diseases.js` — every entry, string
 * and emoji is preserved exactly, now behind the `DiseaseEntry` type so the
 * compiler enforces the schema.
 *
 * One entry was ADDED during the v2.0 restructuring: `Myopia`. The deployed
 * NeuronZero/EyeDiseaseClassifier emits eight classes — AMD, Cataract,
 * Diabetes, Glaucoma, Hypertension, Myopia, Normal, Other — and `Myopia` had no
 * knowledge-base entry, so it previously fell through to the generic default
 * card. Every other entry is untouched.
 *
 * The dual-mode gateway adds a SECOND, separate knowledge base — `HOME_DB` —
 * holding the five Daily Home Mode triage cards. It is deliberately a distinct
 * object rather than extra keys in `DB`, so the clinical entries below remain
 * provably untouched and `getDisease` can resolve either family.
 */

import type { DiseaseEntry } from '@/types/prediction';

/** Knowledge base keyed by canonical condition key. */
export const DB: Record<string, DiseaseEntry> = {
    No_DR: {
        name: 'Healthy Retina', severity: 'healthy', icon: '✅', color: '#10B981',
        desc: 'No signs of diabetic retinopathy detected. Your retina appears healthy.',
        info: 'Clear retinal vasculature, healthy optic disc, no microaneurysms or hemorrhages.',
        recs: [
            { icon: '📅', title: 'Annual Eye Exams', text: 'Continue regular annual eye examinations.', priority: 'routine' },
            { icon: '🩺', title: 'Monitor Blood Sugar', text: 'Keep glucose levels within recommended ranges.', priority: 'routine' },
            { icon: '💊', title: 'Manage Blood Pressure', text: 'Maintain healthy BP levels for retinal health.', priority: 'routine' }
        ],
        habits: [
            { icon: '🥗', title: 'Eye-Healthy Diet', desc: 'Consume omega-3, lutein, zeaxanthin. Include leafy greens and fish.', freq: 'Daily' },
            { icon: '🏃', title: 'Regular Exercise', desc: '30 min moderate exercise maintains healthy blood vessels.', freq: '5x/week' },
            { icon: '😴', title: 'Quality Sleep', desc: '7-8 hours of sleep for overall health and eye function.', freq: 'Nightly' },
            { icon: '🚭', title: 'Avoid Smoking', desc: 'Smoking increases eye disease risk significantly.', freq: 'Always' }
        ],
        prevent: [
            { icon: '🔆', title: 'UV Protection', text: 'Wear UV-protective sunglasses outdoors' },
            { icon: '💧', title: 'Stay Hydrated', text: 'Drink 8 glasses of water daily' },
            { icon: '📱', title: 'Screen Breaks', text: 'Follow 20-20-20 rule' },
            { icon: '🩸', title: 'A1C Monitoring', text: 'Check every 3-6 months' }
        ]
    },
    Mild: {
        name: 'Mild Diabetic Retinopathy', severity: 'warning', icon: '⚠️', color: '#F59E0B',
        desc: 'Early signs detected. Small changes in retinal blood vessels visible.',
        info: 'Microaneurysms detected. This is the earliest clinically visible stage.',
        recs: [
            { icon: '👨‍⚕️', title: 'Schedule Appointment', text: 'See ophthalmologist within 3 months.', priority: 'important' },
            { icon: '📊', title: 'Tighten Glucose', text: 'Target HbA1c below 7%.', priority: 'important' },
            { icon: '📝', title: 'Document Changes', text: 'Log blood sugar and vision changes daily.', priority: 'routine' },
            { icon: '💊', title: 'Review Medications', text: 'Discuss meds with your doctor.', priority: 'routine' }
        ],
        habits: [
            { icon: '🩸', title: 'Blood Sugar Monitoring', desc: 'Fasting: 80-130, post-meal: <180 mg/dL.', freq: '3-4x daily' },
            { icon: '🥬', title: 'Low-Glycemic Diet', desc: 'Whole grains, legumes, non-starchy vegetables.', freq: 'Every meal' },
            { icon: '🚶', title: 'Post-Meal Walking', desc: '15-min walk after meals lowers spikes.', freq: 'After meals' },
            { icon: '📋', title: 'Symptom Journaling', desc: 'Record vision changes, floaters.', freq: 'Weekly' }
        ],
        prevent: [
            { icon: '🎯', title: 'Target HbA1c <7%', text: 'Optimal blood sugar control' },
            { icon: '🧂', title: 'Reduce Sodium', text: 'Control blood pressure' },
            { icon: '🏥', title: 'Regular Check-ups', text: 'Eye exams every 6 months' },
            { icon: '💪', title: 'Stress Management', text: 'Practice relaxation daily' }
        ]
    },
    Moderate: {
        name: 'Moderate Diabetic Retinopathy', severity: 'danger', icon: '🔴', color: '#EF4444',
        desc: 'Visible blood vessel damage affecting the retina detected.',
        info: 'Multiple microaneurysms, hemorrhages, cotton wool spots detected.',
        recs: [
            { icon: '🏥', title: 'Urgent Specialist', text: 'See retinal specialist within 2-4 weeks.', priority: 'urgent' },
            { icon: '📸', title: 'Advanced Imaging', text: 'OCT or fluorescein angiography needed.', priority: 'urgent' },
            { icon: '💉', title: 'Treatment Discussion', text: 'Discuss anti-VEGF or laser therapy.', priority: 'important' },
            { icon: '🔬', title: 'Comprehensive Tests', text: 'Metabolic panel, kidney, lipid tests.', priority: 'important' }
        ],
        habits: [
            { icon: '🩺', title: 'Intensive Monitoring', desc: 'Monitor glucose before and after every meal.', freq: '6-8x daily' },
            { icon: '🥗', title: 'Nutrition Therapy', desc: 'Work with dietitian for personalized plan.', freq: 'Follow plan' },
            { icon: '👁️', title: 'Vision Self-Checks', desc: 'Use Amsler grid for central vision changes.', freq: 'Weekly' },
            { icon: '💊', title: 'Medication Adherence', desc: 'Take all prescriptions as directed.', freq: 'As prescribed' }
        ],
        prevent: [
            { icon: '⚡', title: 'Urgent Care', text: 'Immediate care for sudden changes' },
            { icon: '📉', title: 'BP <130/80', text: 'Strict blood pressure control' },
            { icon: '🚫', title: 'Avoid Straining', text: 'No heavy lifting' },
            { icon: '💤', title: 'Elevate Head', text: 'Sleep with head elevated' }
        ]
    },
    Severe: {
        name: 'Severe Diabetic Retinopathy', severity: 'danger', icon: '🚨', color: '#DC2626',
        desc: 'Significant retinal damage requires immediate medical attention.',
        info: 'Extensive hemorrhages, venous beading, IRMA detected.',
        recs: [
            { icon: '🚑', title: 'Immediate Care', text: 'See retinal specialist within days.', priority: 'urgent' },
            { icon: '💉', title: 'Treatment Required', text: 'Anti-VEGF or laser needed.', priority: 'urgent' },
            { icon: '🏥', title: 'Care Team', text: 'Coordinate specialists.', priority: 'urgent' },
            { icon: '📞', title: 'Emergency Signs', text: 'Know signs of retinal detachment.', priority: 'urgent' }
        ],
        habits: [
            { icon: '🩸', title: 'CGM Monitoring', desc: 'Continuous glucose monitor. Target 70%+ time-in-range.', freq: 'Continuous' },
            { icon: '🥗', title: 'Strict Diet', desc: 'Carb-controlled diet with consistent timing.', freq: 'Every meal' },
            { icon: '👁️', title: 'Daily Vision Checks', desc: 'Check each eye separately every morning.', freq: 'Daily' },
            { icon: '🏃', title: 'Gentle Exercise', desc: 'Low-impact activities only.', freq: 'Daily' }
        ],
        prevent: [
            { icon: '🆘', title: 'Emergency Plan', text: 'Have emergency contacts ready' },
            { icon: '🛡️', title: 'Protect Eyes', text: 'Wear protective eyewear' },
            { icon: '🚷', title: 'Avoid Risks', text: 'No contact sports' },
            { icon: '📱', title: 'Medical Alert', text: 'Consider medical alert bracelet' }
        ]
    },
    Proliferative_DR: {
        name: 'Proliferative Diabetic Retinopathy', severity: 'danger', icon: '🆘', color: '#B91C1C',
        desc: 'Advanced DR with abnormal blood vessel growth. Immediate intervention needed.',
        info: 'Neovascularization detected. Fragile vessels can bleed or cause detachment.',
        recs: [
            { icon: '🚨', title: 'Emergency Treatment', text: 'URGENT: Treatment within days.', priority: 'urgent' },
            { icon: '⚕️', title: 'Retinal Surgeon', text: 'Surgery may be necessary.', priority: 'urgent' },
            { icon: '👀', title: 'Vision Preservation', text: 'Follow advice precisely.', priority: 'urgent' },
            { icon: '🏠', title: 'Recovery Planning', text: 'Arrange support for procedures.', priority: 'important' }
        ],
        habits: [
            { icon: '🩺', title: 'Intensive Care', desc: 'Follow specialist schedule precisely.', freq: 'As scheduled' },
            { icon: '⚠️', title: 'Activity Restrictions', desc: "Follow doctor's restrictions.", freq: 'Always' },
            { icon: '👁️', title: 'Vigilant Monitoring', desc: 'Check vision multiple times daily.', freq: 'Multiple/day' },
            { icon: '🤝', title: 'Support Network', desc: 'Engage family/friends in care.', freq: 'Ongoing' }
        ],
        prevent: [
            { icon: '🏥', title: 'Compliance', text: 'Never miss treatments' },
            { icon: '⚡', title: 'Emergency', text: 'Vision loss = immediate ER' },
            { icon: '🛏️', title: 'Positioning', text: 'Sleep as directed' },
            { icon: '💆', title: 'Stress', text: 'Minimize stress affecting BP' }
        ]
    },
    Glaucoma: {
        name: 'Glaucoma Detected', severity: 'danger', icon: '⚠️', color: '#DC2626',
        desc: 'Glaucoma damages the nerve that connects your eye to your brain. It usually has NO pain or early symptoms — but can cause permanent blindness if untreated.',
        plainName: 'Glaucoma (Optic Nerve Damage)',
        whatIsIt: '👁️ Simply put: Pressure builds up inside your eye and slowly damages your vision from the edges inward — like a closing tunnel.',
        info: 'Signs of increased intraocular pressure and optic nerve damage detected. Early treatment can prevent vision loss.',
        recs: [
            { icon: '🏥', title: 'See an Eye Doctor Soon', text: 'Visit an ophthalmologist within 1–2 weeks. Glaucoma is treatable if caught early.', priority: 'urgent' },
            { icon: '💊', title: 'Eye Drops May Be Prescribed', text: 'Daily eye drops can control eye pressure and stop further damage.', priority: 'important' },
            { icon: '📅', title: 'Regular Pressure Checks', text: 'Get eye pressure measured every 3–6 months.', priority: 'routine' }
        ],
        habits: [
            { icon: '🏃', title: 'Gentle Exercise', desc: 'Regular cardio like walking can reduce eye pressure naturally.', freq: '4x/week' },
            { icon: '💧', title: 'Stay Hydrated', desc: 'Drink water steadily — avoid gulping large amounts at once.', freq: 'Daily' },
            { icon: '😴', title: 'Elevate Head While Sleeping', desc: 'Sleeping with head slightly raised helps reduce eye pressure.', freq: 'Nightly' },
            { icon: '🚭', title: 'Avoid Smoking', desc: 'Smoking worsens blood flow to the optic nerve.', freq: 'Always' }
        ],
        prevent: [
            { icon: '👓', title: 'Never Skip Eye Drops', text: 'If prescribed, use every day without fail' },
            { icon: '🎮', title: 'Limit Screen Glare', text: 'Use anti-glare screens to reduce eye strain' },
            { icon: '☕', title: 'Limit Caffeine', text: 'Excess coffee can temporarily raise eye pressure' },
            { icon: '🏋️', title: 'Avoid Head-Down Poses', text: 'Yoga inversions can spike eye pressure' }
        ]
    },
    AMD: {
        name: 'AMD – Macular Degeneration', severity: 'danger', icon: '🔴', color: '#B91C1C',
        desc: 'AMD affects the central part of your vision — the part you use to read, recognise faces, and see fine details. It does not cause complete blindness but can make everyday tasks very difficult.',
        plainName: 'AMD (Age-Related Macular Degeneration)',
        whatIsIt: '👁️ Simply put: The centre of your retina (called the macula) wears out, creating a blurry or dark patch in the middle of your vision.',
        info: 'Drusen deposits or abnormal blood vessels detected in the macular region. Early intervention preserves central vision.',
        recs: [
            { icon: '👨‍⚕️', title: 'See a Retina Specialist', text: 'Book an appointment with a retinal specialist within 2 weeks.', priority: 'urgent' },
            { icon: '💉', title: 'Injections May Help', text: 'Anti-VEGF injections can slow or reverse wet AMD progression.', priority: 'important' },
            { icon: '🔬', title: 'Amsler Grid Test at Home', text: 'Use an Amsler grid daily to monitor central vision changes.', priority: 'routine' }
        ],
        habits: [
            { icon: '🥦', title: 'Eat Leafy Greens', desc: 'Lutein & zeaxanthin in kale, spinach protect the macula.', freq: 'Daily' },
            { icon: '🐟', title: 'Omega-3 Rich Foods', desc: 'Fish like salmon reduce AMD progression risk.', freq: '3x/week' },
            { icon: '🕶️', title: 'Wear Sunglasses', desc: 'UV rays accelerate AMD — always wear UV-blocking glasses outdoors.', freq: 'Always outdoors' },
            { icon: '🚭', title: 'Stop Smoking', desc: 'Smoking doubles the risk of AMD — the single biggest modifiable risk factor.', freq: 'Always' }
        ],
        prevent: [
            { icon: '💊', title: 'AREDS2 Supplements', text: 'Ask your doctor about vitamin supplements for AMD' },
            { icon: '📱', title: 'Monitor Vision Daily', text: 'Report any new blurriness immediately' },
            { icon: '🔆', title: 'Good Lighting', text: 'Use bright, warm lighting for reading tasks' },
            { icon: '🩺', title: 'Control Blood Pressure', text: 'High BP accelerates AMD damage' }
        ]
    },
    Cataract: {
        name: 'Cataract Detected', severity: 'warning', icon: '🌫️', color: '#D97706',
        desc: 'A cataract is a clouding of the natural lens inside your eye — like looking through a foggy window. It develops slowly and is very treatable with a simple surgery.',
        plainName: 'Cataract (Cloudy Lens)',
        whatIsIt: '👁️ Simply put: The clear lens inside your eye turns cloudy over time, making everything look blurry, faded, or glary — especially at night.',
        info: 'Lens opacity detected indicating cataract formation. Surgical treatment (phacoemulsification) is highly effective.',
        recs: [
            { icon: '👁️', title: 'See an Eye Doctor', text: 'Consult an ophthalmologist to assess cataract severity and discuss surgery timing.', priority: 'important' },
            { icon: '🔦', title: 'Anti-Glare Glasses For Now', text: 'Prescription glasses with anti-reflective coating help in the meantime.', priority: 'routine' },
            { icon: '⏳', title: 'Surgery When Ready', text: 'Cataract surgery is safe, quick (15 mins), and restores vision dramatically.', priority: 'routine' }
        ],
        habits: [
            { icon: '🕶️', title: 'Wear UV Sunglasses', desc: 'UV exposure speeds up cataract development — protect your eyes outdoors.', freq: 'Always outdoors' },
            { icon: '🥕', title: 'Antioxidant-Rich Foods', desc: 'Vitamins C and E (citrus, nuts, seeds) may slow cataract progression.', freq: 'Daily' },
            { icon: '💡', title: 'Better Lighting at Home', desc: 'Bright, focused light makes reading easier with cataracts.', freq: 'Daily' },
            { icon: '🚗', title: 'Avoid Night Driving', desc: 'Cataracts worsen glare from headlights — limit night driving until treated.', freq: 'When possible' }
        ],
        prevent: [
            { icon: '🚭', title: 'No Smoking', text: 'Smoking significantly accelerates cataract formation' },
            { icon: '🍬', title: 'Control Blood Sugar', text: 'Diabetes speeds up cataracts — keep glucose in check' },
            { icon: '🏥', title: 'Regular Eye Exams', text: 'Monitor progression every 6–12 months' },
            { icon: '💊', title: 'Review Your Medications', text: 'Some steroids cause cataracts — discuss with your doctor' }
        ]
    },
    Hypertension: {
        name: 'Hypertensive Retinopathy', severity: 'warning', icon: '🩸', color: '#DC2626',
        desc: 'High blood pressure is damaging the small blood vessels inside your eye. This is called hypertensive retinopathy. It also means your heart and kidneys may be at risk.',
        plainName: 'Hypertension (High Blood Pressure Affecting Eyes)',
        whatIsIt: '👁️ Simply put: Just like high blood pressure damages your heart and kidneys, it also damages the tiny blood vessels at the back of your eye.',
        info: 'Arteriovenous nicking, retinal hemorrhages, or vessel narrowing detected — signs of chronic hypertensive damage.',
        recs: [
            { icon: '🩺', title: 'Check Your Blood Pressure Today', text: 'Visit a doctor to measure your BP. Target is below 130/80 mmHg.', priority: 'urgent' },
            { icon: '💊', title: 'Blood Pressure Medication', text: 'If prescribed, take medication every day — never skip doses.', priority: 'important' },
            { icon: '👁️', title: 'Annual Eye Exams', text: 'Monitor retinal vessel health every year while BP is managed.', priority: 'routine' }
        ],
        habits: [
            { icon: '🧂', title: 'Reduce Salt', desc: 'Limit sodium to under 1500mg/day. Avoid processed and packaged foods.', freq: 'Daily' },
            { icon: '🏃', title: '30 Min Daily Walk', desc: 'Regular moderate exercise lowers blood pressure naturally.', freq: 'Daily' },
            { icon: '😓', title: 'Manage Stress', desc: 'Chronic stress spikes BP — try deep breathing, yoga, or meditation.', freq: 'Daily' },
            { icon: '🍌', title: 'Eat More Potassium', desc: 'Bananas, sweet potatoes, and spinach help control blood pressure.', freq: 'Daily' }
        ],
        prevent: [
            { icon: '🚬', title: 'Stop Smoking', text: 'Each cigarette raises blood pressure immediately' },
            { icon: '🍷', title: 'Limit Alcohol', text: 'Max 1 drink/day for women, 2 for men' },
            { icon: '⚖️', title: 'Maintain Healthy Weight', text: 'Even 5kg weight loss can improve BP significantly' },
            { icon: '☕', title: 'Limit Caffeine', text: 'Coffee can spike BP — limit to 1–2 cups daily' }
        ]
    },
    Diabetes: {
        name: 'Diabetic Eye Signs', severity: 'warning', icon: '🩺', color: '#D97706',
        desc: 'Signs of diabetes-related damage have been found in your retinal blood vessels. This is often an early warning before vision loss occurs — and it is very manageable if caught now.',
        plainName: 'Diabetic Retinopathy (Diabetes Affecting Your Eyes)',
        whatIsIt: '👁️ Simply put: High blood sugar damages the tiny blood vessels at the back of your eye. They swell, leak, or grow abnormally — which can damage your vision over time.',
        info: 'Retinal changes consistent with diabetic retinopathy detected. Blood sugar control is the most important intervention.',
        recs: [
            { icon: '🩸', title: 'Check Your Blood Sugar', text: 'See your doctor to get your HbA1c tested. Target is below 7%.', priority: 'urgent' },
            { icon: '👁️', title: 'See an Eye Doctor', text: 'Get a dilated eye exam from an ophthalmologist within 4 weeks.', priority: 'important' },
            { icon: '💊', title: 'Review Diabetes Management', text: 'Talk to your doctor about adjusting your diabetes treatment plan.', priority: 'important' }
        ],
        habits: [
            { icon: '🍽️', title: 'Low-Glycemic Meals', desc: 'Avoid white rice, sugary drinks, and processed carbs. Choose whole grains and vegetables.', freq: 'Every meal' },
            { icon: '🚶', title: 'Walk After Meals', desc: 'A 15-min walk after eating significantly reduces post-meal blood sugar spikes.', freq: 'After each meal' },
            { icon: '🩸', title: 'Monitor Blood Sugar Daily', desc: 'Track your readings in a log to identify patterns and triggers.', freq: 'Daily' },
            { icon: '😴', title: 'Prioritise Sleep', desc: 'Poor sleep worsens insulin resistance — aim for 7–8 hours.', freq: 'Nightly' }
        ],
        prevent: [
            { icon: '🎯', title: 'Keep HbA1c Below 7%', text: 'This is the single most important prevention step' },
            { icon: '🧂', title: 'Reduce Salt & Sugar', text: 'Protect kidneys and blood vessels together' },
            { icon: '📅', title: 'Annual Eye Exams', text: 'Diabetic eye disease is preventable with early detection' },
            { icon: '🚭', title: 'No Smoking', text: 'Smoking and diabetes together are extremely damaging' }
        ]
    },
    Myopia: {
        name: 'Myopia Detected', severity: 'warning', icon: '👓', color: '#D97706',
        desc: 'Signs of myopia (short-sightedness) were found. Distant objects look blurry because the eye focuses light in front of the retina instead of on it. High myopia also stretches the retina, which raises the risk of other eye problems later.',
        plainName: 'Myopia (Short-Sightedness)',
        whatIsIt: '👁️ Simply put: Your eyeball is slightly too long for its focusing power, so far-away things look blurry while close-up things stay sharp.',
        info: 'Retinal features consistent with myopic refractive error detected, such as a tilted optic disc or peripapillary atrophy. Corrective lenses and monitoring are the standard response.',
        recs: [
            { icon: '👓', title: 'Get a Refraction Test', text: 'An optometrist can measure your prescription and fit glasses or contact lenses.', priority: 'important' },
            { icon: '👁️', title: 'Dilated Retinal Exam', text: 'High myopia stretches the retina — ask for a peripheral retinal check.', priority: 'important' },
            { icon: '📅', title: 'Annual Monitoring', text: 'Re-check your prescription every year; myopia can progress over time.', priority: 'routine' }
        ],
        habits: [
            { icon: '🌳', title: 'Time Outdoors', desc: 'Daylight exposure slows myopia progression, especially in younger eyes.', freq: '2 hrs daily' },
            { icon: '📱', title: '20-20-20 Screen Rule', desc: 'Every 20 mins, look 20 feet away for 20 seconds to relax focusing muscles.', freq: 'Every 20 mins' },
            { icon: '💡', title: 'Good Reading Light', desc: 'Read in bright, even light and hold material at least 30cm from your eyes.', freq: 'Daily' },
            { icon: '👓', title: 'Wear Your Correction', desc: 'Consistently wearing the right prescription reduces eye strain and headaches.', freq: 'Always' }
        ],
        prevent: [
            { icon: '⚠️', title: 'Watch for Flashes or Floaters', text: 'Sudden flashes, floaters or a shadow need same-day attention' },
            { icon: '🕶️', title: 'UV Protection', text: 'Wear UV400 sunglasses outdoors' },
            { icon: '🏃', title: 'Break Up Near Work', text: 'Alternate close work with distance viewing' },
            { icon: '🏥', title: 'Regular Eye Exams', text: 'High myopia needs retinal checks every 12 months' }
        ]
    },
    Other: {
        name: 'Other Finding Detected', severity: 'warning', icon: '🔍', color: '#6366F1',
        desc: 'The AI detected something unusual in your retinal image that does not match a specific known pattern. This does not necessarily mean something is seriously wrong — but it is worth getting checked by a doctor.',
        plainName: 'Unclassified Finding (Needs Professional Review)',
        whatIsIt: '👁️ Simply put: Your eye scan shows something the AI cannot fully classify. Think of it like an X-ray showing a shadow — a doctor needs to look and confirm.',
        info: 'Retinal features detected that do not fit major disease categories. Professional evaluation is recommended.',
        recs: [
            { icon: '👨‍⚕️', title: 'See an Eye Doctor', text: 'Book an appointment for a full dilated eye exam to clarify this finding.', priority: 'important' },
            { icon: '📄', title: 'Bring This Report', text: 'Download and share this report with your ophthalmologist.', priority: 'routine' },
            { icon: '📅', title: 'Do Not Delay', text: 'Even if you have no symptoms, early professional evaluation is always best.', priority: 'routine' }
        ],
        habits: [
            { icon: '👁️', title: 'Regular Self-Checks', desc: 'Cover each eye and check vision separately — report any new changes.', freq: 'Weekly' },
            { icon: '🥗', title: 'Eye-Healthy Diet', desc: 'Lutein, Omega-3, and antioxidants support retinal health.', freq: 'Daily' },
            { icon: '💧', title: 'Stay Hydrated', desc: 'Good hydration supports healthy eye tissue.', freq: 'Daily' },
            { icon: '🔆', title: 'Reduce Screen Strain', desc: 'Follow the 20-20-20 rule: every 20 mins, look 20 feet away for 20 seconds.', freq: 'Every 20 mins' }
        ],
        prevent: [
            { icon: '🕶️', title: 'Wear UV Sunglasses', text: 'Protect eyes from sun damage year-round' },
            { icon: '🏥', title: 'Routine Eye Exams', text: 'Annual check-ups catch problems before symptoms appear' },
            { icon: '🚭', title: 'Avoid Smoking', text: 'Smoking is a top risk factor for most eye diseases' },
            { icon: '🩺', title: 'Control Chronic Conditions', text: 'Manage BP, diabetes, and cholesterol for eye health' }
        ]
    },
    Healthy_Retina: {
        name: 'Healthy Retina', severity: 'healthy', icon: '✅', color: '#10B981',
        desc: 'Great news! No signs of eye disease were detected. Your retina looks healthy. Keep up the good work and continue with regular eye check-ups.',
        plainName: 'Healthy Retina (No Disease Found)',
        whatIsIt: '👁️ Simply put: Your retinal scan shows no signs of any known eye disease. Your eyes look healthy!',
        info: 'No significant retinal pathology detected. Normal vasculature, clear optic disc, no hemorrhages or lesions.',
        recs: [
            { icon: '📅', title: 'Keep Up Annual Eye Exams', text: 'Even healthy eyes benefit from yearly professional check-ups.', priority: 'routine' },
            { icon: '🥗', title: 'Maintain Healthy Habits', text: 'Good nutrition and exercise protect your eyes long-term.', priority: 'routine' },
            { icon: '🕶️', title: 'Protect From UV', text: 'Always wear UV-blocking sunglasses outdoors.', priority: 'routine' }
        ],
        habits: [
            { icon: '🥦', title: 'Eat Eye-Healthy Foods', desc: 'Leafy greens, carrots, fish and nuts support long-term retinal health.', freq: 'Daily' },
            { icon: '🏃', title: 'Stay Active', desc: 'Regular exercise improves circulation to your eyes.', freq: '5x/week' },
            { icon: '😴', title: 'Sleep Well', desc: '7–8 hours of sleep lets your eyes recover and repair.', freq: 'Nightly' },
            { icon: '📱', title: '20-20-20 Screen Rule', desc: 'Every 20 mins, look 20 feet away for 20 seconds to rest your eyes.', freq: 'Every 20 mins' }
        ],
        prevent: [
            { icon: '🔆', title: 'UV Protection', text: 'Wear sunglasses rated UV400 or higher' },
            { icon: '🚭', title: 'Avoid Smoking', text: 'Smoking is the top preventable risk for eye disease' },
            { icon: '🩺', title: 'Control Blood Pressure', text: 'Healthy BP protects your retinal vessels' },
            { icon: '💧', title: 'Stay Hydrated', text: 'Drink 8 glasses of water daily' }
        ]
    },
    default: {
        name: 'Analysis Result', severity: 'warning', icon: '🔍', color: '#6366F1',
        desc: 'AI has analyzed your image. Consult a healthcare professional for a proper evaluation.',
        info: 'Classification based on detected features. Professional medical review is recommended.',
        recs: [
            { icon: '👨‍⚕️', title: 'Consult an Eye Doctor', text: 'Have these results reviewed by a qualified ophthalmologist.', priority: 'important' },
            { icon: '📋', title: 'Share This Report', text: 'Download and bring this report to your doctor appointment.', priority: 'routine' }
        ],
        habits: [
            { icon: '👁️', title: 'Regular Eye Care', desc: 'Maintain annual eye examinations.', freq: 'Yearly' },
            { icon: '🥗', title: 'Healthy Lifestyle', desc: 'Balanced diet and regular exercise support eye health.', freq: 'Daily' }
        ],
        prevent: [
            { icon: '🏥', title: 'Regular Check-ups', text: 'Schedule routine eye exams every year' },
            { icon: '🔆', title: 'Protect Your Eyes', text: 'Wear appropriate UV-protective eyewear' }
        ]
    }
};

// ═══════════════════════════════════════════════════════════════════════════
// DAILY HOME MODE — 5 TRIAGE CARDS
// ═══════════════════════════════════════════════════════════════════════════
//
// These are NOT diagnoses. Each card is a plain-language triage bucket scored
// by the rule engine in `backend/triage.py`; the keys here are that engine's
// wire contract, so the two files must be renamed together or not at all.
//
// The home scale has five urgency bands where the clinical scale has three, so
// every entry carries an explicit `badge` override.

/** Knowledge base for the Daily Home Mode cards, keyed by triage card id. */
export const HOME_DB: Record<string, DiseaseEntry> = {
    Home_Healthy: {
        name: 'Your Eyes Look Healthy', severity: 'healthy', icon: '✅', color: '#10B981',
        mode: 'home',
        badge: { label: 'Healthy', color: '#047857', background: 'rgba(16,185,129,0.14)' },
        covers: 'AI analysis found no visible signs of common eye diseases in your photo.',
        plainName: 'Healthy eye',
        whatIsIt: 'Our AI model examined your photo and found no signs of disease.',
        desc: 'Great news — the AI analysis of your eye photo did not detect signs of common eye conditions. Keep up your healthy eye habits and schedule routine check-ups.',
        info: 'The NeuronZero eye disease classifier examined your photo and classified it as "Normal" with high confidence. This means no visible indicators of AMD, cataracts, glaucoma, diabetic retinopathy, hypertension, or myopia were detected.',
        recs: [
            { icon: '📅', title: 'Annual Eye Exam', text: 'Even when everything looks good, schedule a comprehensive eye exam once a year. Early detection of conditions like glaucoma requires professional equipment.', priority: 'routine' },
            { icon: '😎', title: 'UV Protection', text: 'Wear UV400 sunglasses outdoors to protect against long-term UV damage to the lens and retina.', priority: 'routine' },
            { icon: '🥬', title: 'Eye-Healthy Diet', text: 'Leafy greens, omega-3 fish, and colourful vegetables support retinal health and reduce disease risk.', priority: 'routine' }
        ],
        habits: [
            { icon: '⏱️', title: '20-20-20 Rule', desc: 'Every 20 minutes of screen time, look at something 20 feet away for 20 seconds.', freq: 'During screen use' },
            { icon: '💧', title: 'Stay Hydrated', desc: 'Adequate water intake supports healthy tear production and prevents dryness.', freq: 'Daily' },
            { icon: '😴', title: '7–8 Hours Sleep', desc: 'Quality sleep allows your eyes to rest, repair and relubricate overnight.', freq: 'Nightly' }
        ],
        prevent: [
            { icon: '🚭', title: 'Don\'t Smoke', text: 'Smoking doubles the risk of cataracts and triples the risk of AMD' },
            { icon: '🩺', title: 'Know Your Numbers', text: 'Blood sugar and blood pressure directly affect eye health' },
            { icon: '👨‍👩‍👧', title: 'Family History', text: 'If glaucoma or macular degeneration runs in your family, get screened more often' },
            { icon: '📱', title: 'Screen Breaks', text: 'Long screen hours are the leading cause of eye strain — take regular breaks' }
        ]
    },

    Home_Allergy_Irritation: {
        name: 'Itchiness & Allergic Surface Relief', severity: 'healthy', icon: '🌿', color: '#06B6D4',
        mode: 'home',
        badge: { label: 'Mild', color: '#0E7490', background: 'rgba(6,182,212,0.14)' },
        covers: 'Dust, pollen, seasonal allergies, gritty or watering sensations.',
        plainName: 'Allergy eye',
        whatIsIt: 'Your eye surface is irritated by something in the air, not by disease.',
        desc: 'Your answers point to ordinary surface irritation — the kind allergies, dust and pollen cause. This settles at home in a few days.',
        info: 'Allergic conjunctivitis and simple surface irritation affect the outermost layer of the eye. The itching comes from histamine released by the conjunctiva; it does not involve the retina or the optic nerve.',
        recs: [
            { icon: '💧', title: 'Lubricating Eye Drops', text: 'Use preservative-free lubricating drops to flush allergens off the surface.', priority: 'routine' },
            { icon: '🧊', title: 'Cold Compress', text: 'Hold a cold compress over closed eyelids for 5–10 minutes to calm the itch.', priority: 'routine' },
            { icon: '🚫', title: 'The No-Rubbing Rule', text: 'Do not rub. Rubbing causes micro-scratches on the cornea and makes the itching worse.', priority: 'important' }
        ],
        habits: [
            { icon: '🪟', title: 'Close Windows on High-Pollen Days', desc: 'Check the local pollen count and keep windows shut in the morning, when counts peak.', freq: 'Seasonal' },
            { icon: '🚿', title: 'Rinse After Coming Indoors', desc: 'Splash your face and rinse your eyelids to wash off settled pollen.', freq: 'Daily' },
            { icon: '🛏️', title: 'Wash Bedding Weekly', desc: 'Hot-wash pillowcases to cut dust-mite exposure while you sleep.', freq: 'Weekly' }
        ],
        prevent: [
            { icon: '😎', title: 'Wrap-Around Sunglasses', text: 'They block airborne pollen as well as UV' },
            { icon: '🧴', title: 'Keep Drops Handy', text: 'Treat early, before the itch-rub cycle starts' },
            { icon: '🐾', title: 'Mind Pet Dander', text: 'Keep pets off the bed if your eyes flare overnight' },
            { icon: '👨‍⚕️', title: 'See Someone If It Persists', text: 'Itching beyond two weeks deserves a proper look' }
        ]
    },

    Home_Digital_Strain: {
        name: 'Digital Eye Strain & Dry Eye Syndrome', severity: 'warning', icon: '📱', color: '#F59E0B',
        mode: 'home',
        badge: { label: 'Moderate', color: '#B45309', background: 'rgba(245,158,11,0.16)' },
        covers: 'Screen glare, reduced blinking, burning sensation, tired evening eyes.',
        plainName: 'Screen fatigue',
        whatIsIt: 'Long screen sessions cut your blink rate roughly in half, so the tear film dries out.',
        desc: 'Your answers match digital eye strain: the tired, burning, end-of-day eyes that come from long screen sessions and too few blinks.',
        info: 'Sustained near-focus holds the ciliary muscle contracted while the blink rate drops from ~15 to ~6 per minute. The tear film evaporates between blinks, producing burning, grittiness and blur that clears when you look away.',
        recs: [
            { icon: '⏱️', title: 'The 20-20-20 Rule', text: 'Every 20 minutes, look at something 20 feet away for 20 seconds. This is the single most effective fix.', priority: 'important' },
            { icon: '💧', title: 'Hydrate & Warm Compress', text: 'Eight glasses of water through the day, plus a warm towel compress in the evening.', priority: 'routine' },
            { icon: '💡', title: 'Fix Your Lighting', text: 'Match screen brightness to the room and warm the display colour temperature after dark.', priority: 'routine' }
        ],
        habits: [
            { icon: '👁️', title: 'Blink Deliberately', desc: 'Ten slow, full blinks every half hour re-spreads the tear film across the cornea.', freq: 'Hourly' },
            { icon: '📐', title: 'Arm’s-Length Screen', desc: 'Keep the monitor 50–70 cm away with the top edge at or just below eye level.', freq: 'Always' },
            { icon: '🌙', title: 'Night Mode After Sunset', desc: 'Warmer colour temperature in the evening eases both strain and sleep onset.', freq: 'Nightly' },
            { icon: '💦', title: 'Humidify Dry Rooms', desc: 'Air conditioning and heating both strip moisture from the tear film.', freq: 'Daily' }
        ],
        prevent: [
            { icon: '🪑', title: 'Sort Your Ergonomics', text: 'Screen height and distance matter more than blue-light filters' },
            { icon: '🚭', title: 'Avoid Smoke & Direct Air', text: 'Keep fans and vents from blowing across your face' },
            { icon: '🐟', title: 'Omega-3 In Your Diet', text: 'Supports the oily layer that stops tears evaporating' },
            { icon: '👓', title: 'Get Your Prescription Checked', text: 'An out-of-date prescription doubles the strain' }
        ]
    },

    Home_Red_Eye: {
        name: 'Bloodshot Red Eye & Conjunctivitis', severity: 'warning', icon: '🩸', color: '#F97316',
        mode: 'home',
        badge: { label: 'Warning', color: '#C2410C', background: 'rgba(249,115,22,0.16)' },
        covers: 'Prominent vascular flare, bloodshot white sclera, bacterial or viral pink eye, or a broken superficial vessel (subconjunctival haemorrhage).',
        plainName: 'Pink eye / red eye',
        whatIsIt: 'The surface vessels of the white of your eye are inflamed or one has broken.',
        desc: 'Your answers point to an inflamed or bloodshot eye surface. Much of this clears on its own, but it can be contagious — treat hygiene as the priority.',
        info: 'Dilated conjunctival vessels produce the diffuse redness of conjunctivitis; a sharply bordered bright-red patch instead indicates a subconjunctival haemorrhage, which is harmless and clears in 1–2 weeks. Neither involves the retina.',
        recs: [
            { icon: '🧼', title: 'Hygiene Protocol', text: 'Separate towels and pillowcases, and wash hands often — viral pink eye spreads easily through a household.', priority: 'important' },
            { icon: '💧', title: 'Sterile Saline Flush', text: 'Rinse with sterile saline. Do not wear contact lenses until the redness has fully cleared.', priority: 'important' },
            { icon: '👨‍⚕️', title: 'Ask About Antibiotic Drops', text: 'Waking with crusty or yellow discharge suggests a bacterial cause. See a pharmacist or doctor.', priority: 'urgent' }
        ],
        habits: [
            { icon: '🤲', title: 'Wash Hands Before Touching', desc: 'Most household transmission happens hand-to-eye, not through the air.', freq: 'Always' },
            { icon: '🧺', title: 'Change Pillowcases Daily', desc: 'While symptoms last, a fresh pillowcase each night prevents re-infection.', freq: 'Daily' },
            { icon: '💄', title: 'Bin Old Eye Make-Up', desc: 'Mascara and liner used during an infection will re-seed it. Replace them.', freq: 'Once' },
            { icon: '🕶️', title: 'Skip Lenses, Wear Glasses', desc: 'Give the cornea a full break until the eye is white again.', freq: 'Until clear' }
        ],
        prevent: [
            { icon: '🚿', title: 'Never Share Towels', text: 'The most common route of spread in a family' },
            { icon: '📵', title: 'Clean Your Phone Screen', text: 'It touches your face more than anything else you own' },
            { icon: '💦', title: 'Lens Hygiene', text: 'Fresh solution every time — never top up an old case' },
            { icon: '⏳', title: 'Give It A Week', text: 'Redness lasting beyond 7–10 days needs examining' }
        ]
    },

    Home_Lens_Haze: {
        name: 'Visible Lens Cloudiness & Pupil Haze', severity: 'warning', icon: '🌫️', color: '#8B5CF6',
        mode: 'home',
        badge: { label: 'Chronic Attention', color: '#6D28D9', background: 'rgba(139,92,246,0.16)' },
        covers: 'Visible milky or greyish clouding over the pupil in a phone photo, faded colours, night-driving halos, early cataract symptoms in elderly parents.',
        plainName: 'Early cataract signs',
        whatIsIt: 'The natural lens behind the pupil is clouding, so less light reaches the retina.',
        desc: 'Your answers suggest clouding of the lens itself. This develops slowly over years, is not an emergency, and is corrected with a routine, highly successful operation.',
        info: 'Cataract is an age-related opacification of the crystalline lens. It scatters incoming light — hence the halos and faded colours — long before it blocks vision outright. It cannot be reversed by drops, but lens replacement restores sight in the large majority of cases.',
        recs: [
            { icon: '🚗', title: 'Avoid Night Driving', text: 'If oncoming headlight glare is severe, stop driving after dark until you have been assessed.', priority: 'important' },
            { icon: '👓', title: 'Anti-Reflective UV400 Lenses', text: 'Anti-glare prescription lenses give real, if temporary, relief from scatter.', priority: 'routine' },
            { icon: '👁️', title: 'Book an Ophthalmologist', text: 'Have the cataract graded for maturity so surgical replacement can be planned at the right time.', priority: 'important' }
        ],
        habits: [
            { icon: '🔆', title: 'Brighter Task Lighting', desc: 'Direct light on books and work compensates for the light the lens is scattering.', freq: 'Daily' },
            { icon: '😎', title: 'UV Protection Outdoors', desc: 'UV exposure accelerates lens clouding — sunglasses slow the progression.', freq: 'Daily' },
            { icon: '🥬', title: 'Antioxidant-Rich Diet', desc: 'Leafy greens, citrus and colourful vegetables support lens clarity.', freq: 'Daily' },
            { icon: '🩸', title: 'Keep Blood Sugar Steady', desc: 'Diabetes brings cataract forward by years; good control delays it.', freq: 'Ongoing' }
        ],
        prevent: [
            { icon: '🚭', title: 'Stop Smoking', text: 'The strongest modifiable risk factor for cataract' },
            { icon: '📅', title: 'Yearly Eye Exams After 60', text: 'Catches the change while glasses still help' },
            { icon: '💊', title: 'Review Long-Term Steroids', text: 'Ask your doctor — they can accelerate clouding' },
            { icon: '🚫', title: 'Ignore "Cataract Drops"', text: 'No eye drop dissolves a cataract. Only surgery does' }
        ]
    },

    Home_Vision_Loss_Alert: {
        name: 'Early Vision Loss Red-Alert', severity: 'danger', icon: '🚨', color: '#DC2626',
        mode: 'home',
        badge: { label: 'High Urgency', color: '#B91C1C', background: 'rgba(220,38,38,0.16)' },
        covers: 'Sudden blurriness, floating dark webs or spots, tunnel vision, or a history of diabetes combined with vascular symptoms.',
        plainName: 'Urgent warning signs',
        whatIsIt: 'These symptoms come from the back of the eye — the retina and optic nerve — not the surface.',
        desc: 'Do not treat this with home drops. What you have described are warning signs of retinal or optic-nerve distress, such as diabetic retinopathy or glaucoma. Get examined today.',
        info: 'Sudden blur, a shower of new floaters, flashes or a narrowing field all originate behind the lens. Retinal detachment, vitreous haemorrhage and acute glaucoma are time-critical: the window in which sight can be saved is measured in hours to days, and there is no home remedy for any of them.',
        recs: [
            { icon: '🏥', title: 'Immediate Hospital Escalation', text: 'Do not treat with home drops. These are warning signs of retinal or optic nerve distress (such as Diabetic Retinopathy or Glaucoma). Go to an eye casualty or emergency department today.', priority: 'urgent' },
            { icon: '🔄', title: 'Run a Clinical Scan Now', text: 'If you have a fundus or OCT image, switch to Clinical Retinal Scan mode for a RETFound analysis while you arrange the appointment.', priority: 'urgent' },
            { icon: '🩸', title: 'Check HbA1c and Blood Pressure', text: 'Bring recent blood sugar (HbA1c) and blood pressure readings with you — both drive retinal damage.', priority: 'important' }
        ],
        habits: [
            { icon: '📝', title: 'Write Down What Changed', desc: 'Note exactly when the symptoms started and which eye. This shapes the diagnosis.', freq: 'Now' },
            { icon: '🚗', title: 'Do Not Drive Yourself', desc: 'Ask someone to take you. Sudden visual change makes driving unsafe.', freq: 'Now' },
            { icon: '💊', title: 'Bring Your Medication List', desc: 'Include diabetes and blood-pressure medication with doses.', freq: 'Now' },
            { icon: '📵', title: 'Do Not Wait and See', desc: 'Delay is the single biggest cause of permanent loss in these conditions.', freq: 'Now' }
        ],
        prevent: [
            { icon: '🩺', title: 'Annual Dilated Exam', text: 'Essential every year if you are diabetic' },
            { icon: '📉', title: 'Control Blood Sugar', text: 'Tight HbA1c control measurably slows retinopathy' },
            { icon: '❤️', title: 'Control Blood Pressure', text: 'Hypertension compounds every retinal vascular risk' },
            { icon: '👨‍👩‍👧', title: 'Know Your Family History', text: 'Glaucoma runs in families and is silent until late' }
        ]
    }
};

/**
 * Report whether a label belongs to the Daily Home Mode card family.
 *
 * @param label Raw label from either engine.
 * @returns True when the label resolves to a `HOME_DB` entry.
 */
export function isHomeCard(label: string): boolean {
  return label in HOME_DB;
}

/**
 * Resolve a raw model label to its knowledge-base entry.
 *
 * Home triage card ids are matched first and exactly — they are generated by
 * our own rule engine, never by a classifier, so they need no normalisation.
 * Everything else falls through to the clinical resolver below.
 *
 * Normalises case and separators, then maps known model-label aliases onto
 * canonical keys. Unknown labels fall back to the generic `default` entry with
 * the label prettified as its name, so the UI never renders an empty card.
 *
 * @param label Raw label from the classifier, e.g. "Healthy_Retina".
 * @returns The matching knowledge-base entry, never null.
 */
export function getDisease(label: string): DiseaseEntry {
  const homeEntry = HOME_DB[label];
  if (homeEntry) return homeEntry;

  const norm = (label || '').toLowerCase().replace(/[_\s-]+/g, '_');
  const map: Record<string, string> = {
    // Diabetic Retinopathy variants
    no_dr: 'No_DR', mild: 'Mild', mild_dr: 'Mild',
    moderate: 'Moderate', moderate_dr: 'Moderate',
    severe: 'Severe', severe_dr: 'Severe',
    proliferative_dr: 'Proliferative_DR', proliferative: 'Proliferative_DR',
    // Healthy
    healthy: 'Healthy_Retina', normal: 'Healthy_Retina', healthy_retina: 'Healthy_Retina',
    // Model labels
    glaucoma: 'Glaucoma',
    amd: 'AMD', age_related_macular_degeneration: 'AMD', macular_degeneration: 'AMD',
    cataract: 'Cataract', cataracts: 'Cataract',
    hypertension: 'Hypertension', hypertensive_retinopathy: 'Hypertension',
    diabetes: 'Diabetes', diabetic_retinopathy: 'Diabetes', dr: 'Diabetes',
    myopia: 'Myopia', pathological_myopia: 'Myopia', nearsightedness: 'Myopia',
    other: 'Other', unknown: 'Other',
  };
  const key = map[norm] ?? label;
  const entry = DB[key];
  if (entry) return entry;

  return {
    ...DB.default,
    name: label.replace(/_/g, ' ').replace(/\w/g, (c) => c.toUpperCase()),
  };
}
