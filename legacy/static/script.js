/**
 * VisionAI - Eye Hospital Landing Page
 * Modern JavaScript with Navigation & AI Screening
 * Version 4.0
 */

// ═══════════════════════════════════════════════════════════════════════════════
// CSRF TOKEN HELPER
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * Retrieves the CSRF token from the meta tag injected by Flask-WTF.
 * Returns an empty string if the meta tag is not present (e.g., on pages
 * that don't require CSRF protection).
 */
function getCSRFToken() {
    return document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
}

// ═══════════════════════════════════════════════════════════════════════════════
// DISEASE KNOWLEDGE BASE
// ═══════════════════════════════════════════════════════════════════════════════

const DB = {
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
            { icon: '⚠️', title: 'Activity Restrictions', desc: 'Follow doctor\'s restrictions.', freq: 'Always' },
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
    // ── NEW MODEL LABELS ──────────────────────────────────────────────────────
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

// ═══════════════════════════════════════════════════════════════════════════════
// STATE & INITIALIZATION
// ═══════════════════════════════════════════════════════════════════════════════

const State = { file: null, analyzing: false, result: null };

document.addEventListener('DOMContentLoaded', () => {
    console.log('🚀 VisionAI Initialized');
    initNavigation();
    initTheme();
    initUpload();
    initActions();
    fetch('/config').then(r => r.json()).then(c => console.log('📋 Config:', c)).catch(() => { });
});

// ═══════════════════════════════════════════════════════════════════════════════
// NAVIGATION
// ═══════════════════════════════════════════════════════════════════════════════

function initNavigation() {
    // Smooth scroll for nav links
    document.querySelectorAll('a[href^="#"]').forEach(link => {
        link.addEventListener('click', e => {
            e.preventDefault();
            const target = document.querySelector(link.getAttribute('href'));
            if (target) {
                const offset = 80;
                const pos = target.getBoundingClientRect().top + window.pageYOffset - offset;
                window.scrollTo({ top: pos, behavior: 'smooth' });
            }
        });
    });

    // Active nav link on scroll
    const sections = document.querySelectorAll('section[id]');
    window.addEventListener('scroll', () => {
        const scrollPos = window.scrollY + 100;
        sections.forEach(section => {
            const top = section.offsetTop;
            const height = section.offsetHeight;
            const id = section.getAttribute('id');
            const link = document.querySelector(`.nav-link[href="#${id}"]`);
            if (link) {
                link.classList.toggle('active', scrollPos >= top && scrollPos < top + height);
            }
        });

        // Navbar background on scroll
        const navbar = document.getElementById('navbar');
        if (navbar) {
            navbar.style.boxShadow = window.scrollY > 50 ? 'var(--shadow-md)' : 'none';
        }
    });

    // Mobile menu toggle
    const toggle = document.getElementById('navToggle');
    const links = document.getElementById('navLinks');
    if (toggle && links) {
        toggle.addEventListener('click', () => {
            links.classList.toggle('active');
        });
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
// THEME
// ═══════════════════════════════════════════════════════════════════════════════

function initTheme() {
    const btn = document.getElementById('themeToggle');
    if (!btn) return;

    const saved = localStorage.getItem('theme');
    const sysDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    if (saved) document.documentElement.setAttribute('data-theme', saved);
    else if (sysDark) document.documentElement.setAttribute('data-theme', 'dark');

    btn.addEventListener('click', () => {
        const curr = document.documentElement.getAttribute('data-theme');
        const next = curr === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', next);
        localStorage.setItem('theme', next);
        btn.style.transform = 'scale(1.1) rotate(180deg)';
        setTimeout(() => btn.style.transform = '', 300);
    });

    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', e => {
        if (!localStorage.getItem('theme')) {
            document.documentElement.setAttribute('data-theme', e.matches ? 'dark' : 'light');
        }
    });
}

// ═══════════════════════════════════════════════════════════════════════════════
// UPLOAD
// ═══════════════════════════════════════════════════════════════════════════════

function initUpload() {
    const input = document.getElementById('imageInput');
    const area = document.getElementById('uploadArea');
    const btn = document.getElementById('uploadBtn');
    const preview = document.getElementById('imagePreview');
    const img = document.getElementById('previewImg');
    const remove = document.getElementById('removeImage');

    if (!input || !area) return;

    btn?.addEventListener('click', e => { e.stopPropagation(); input.click(); });
    area.addEventListener('click', () => input.click());
    input.addEventListener('change', e => e.target.files[0] && handleFile(e.target.files[0]));
    remove?.addEventListener('click', reset);

    // Drag & drop
    ['dragover', 'dragenter'].forEach(e => area.addEventListener(e, ev => { ev.preventDefault(); area.classList.add('dragover'); }));
    ['dragleave', 'dragend'].forEach(e => area.addEventListener(e, ev => { ev.preventDefault(); area.classList.remove('dragover'); }));
    area.addEventListener('drop', e => {
        e.preventDefault();
        area.classList.remove('dragover');
        e.dataTransfer.files[0] && handleFile(e.dataTransfer.files[0]);
    });
}

function handleFile(file) {
    const input = document.getElementById('imageInput');
    const area = document.getElementById('uploadArea');
    const preview = document.getElementById('imagePreview');
    const img = document.getElementById('previewImg');

    const valid = validateFile(file);
    if (!valid.ok) return showError(valid.error);

    State.file = file;
    const reader = new FileReader();
    reader.onload = e => {
        img.src = e.target.result;
        preview.style.display = 'flex';
        area.style.display = 'none';
        setTimeout(analyze, 500);
    };
    reader.readAsDataURL(file);
}

function validateFile(file) {
    if (!file) return { ok: false, error: 'No file selected' };
    const types = ['image/png', 'image/jpeg', 'image/jpg', 'image/bmp', 'image/tiff', 'image/webp'];
    if (!types.includes(file.type.toLowerCase())) return { ok: false, error: 'Unsupported format. Use PNG, JPG, BMP, TIFF, or WEBP' };
    if (file.size > 16 * 1024 * 1024) return { ok: false, error: 'File too large. Max 16MB' };
    return { ok: true };
}

// ═══════════════════════════════════════════════════════════════════════════════
// ANALYSIS
// ═══════════════════════════════════════════════════════════════════════════════

async function analyze() {
    if (!State.file || State.analyzing) return;
    State.analyzing = true;

    const section = document.getElementById('analysisSection');
    const loading = document.getElementById('loading');
    const results = document.getElementById('results');
    const error = document.getElementById('error');

    section.style.display = 'block';
    loading.style.display = 'block';
    results.style.display = 'none';
    error.style.display = 'none';

    // Scroll to analysis section
    section.scrollIntoView({ behavior: 'smooth', block: 'start' });

    try {
        const form = new FormData();
        form.append('image', State.file);

        // CRITICAL: Include credentials (session cookies) and CSRF token with the request
        const res = await fetch('/predict', {
            method: 'POST',
            headers: { 'X-CSRFToken': getCSRFToken() },
            body: form,
            credentials: 'same-origin'  // This sends cookies with the request
        });

        // Check if we got redirected to login (authentication issue)
        if (res.redirected || res.url.includes('/login')) {
            loading.style.display = 'none';
            showError('Session expired. Please refresh and login again.');
            setTimeout(() => window.location.href = '/login', 2000);
            return;
        }

        // Check content type - if HTML, session expired
        const contentType = res.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            loading.style.display = 'none';
            showError('Session expired. Redirecting to login...');
            setTimeout(() => window.location.href = '/login', 2000);
            return;
        }

        const data = await res.json();

        loading.style.display = 'none';

        if (data.success && data.predictions) {
            State.result = data;
            showResults(data.predictions);
        } else {
            showError(data.error || 'Analysis failed');
        }
    } catch (e) {
        loading.style.display = 'none';
        showError('Network error. Check connection.');
        console.error('Analysis error:', e);
    }
    State.analyzing = false;
}

// ═══════════════════════════════════════════════════════════════════════════════
// RESULTS DISPLAY
// ═══════════════════════════════════════════════════════════════════════════════

function showResults(preds) {
    const results = document.getElementById('results');
    const primary = document.getElementById('primaryDiagnosis');
    const predsEl = document.getElementById('predictions');

    if (!preds?.length) return showError('No results');
    results.style.display = 'block';

    const top = preds[0];
    const d = getDisease(top.label);

    // Primary diagnosis
    primary.innerHTML = `
        <div style="display:flex;align-items:center;gap:var(--space-3);margin-bottom:var(--space-4)">
            <span style="font-size:2rem">${d.icon}</span>
            <div>
                <div style="font-size:0.875rem;opacity:0.9">Primary Finding</div>
                <div style="font-size:1.5rem;font-weight:700">${d.name}</div>
            </div>
        </div>
        <p style="opacity:0.9;margin-bottom:var(--space-4)">${d.desc}</p>
        <div style="background:rgba(255,255,255,0.2);border-radius:var(--radius-lg);padding:var(--space-3)">
            <div style="display:flex;justify-content:space-between;margin-bottom:var(--space-2);font-size:0.875rem">
                <span>AI Match Score</span>
                <span>${(top.confidence || 0).toFixed(1)}%</span>
            </div>
            <div style="height:8px;background:rgba(255,255,255,0.3);border-radius:var(--radius-full);overflow:hidden">
                <div style="height:100%;width:${Math.min(top.confidence || 0, 100)}%;background:linear-gradient(90deg,#2dd4bf,#10b981);border-radius:var(--radius-full)"></div>
            </div>
        </div>
    `;
    primary.style.background = `linear-gradient(135deg, ${d.color}, ${darken(d.color, 20)})`;

    // Prediction cards
    predsEl.innerHTML = preds.map((p, i) => {
        const dis = getDisease(p.label);
        return `
        <div class="disease-card ${i === 0 ? 'expanded' : ''}" id="card-${i}">
            <div class="disease-card-header" onclick="toggle('card-${i}')">
                <div class="disease-icon-wrapper ${dis.severity}"><span class="disease-icon">${dis.icon}</span></div>
                <div class="disease-info">
                    <h4 class="disease-name">${dis.name}</h4>
                    <span class="disease-severity ${dis.severity}">${cap(dis.severity)}</span>
                </div>
                <div class="disease-confidence">
                    <span class="confidence-value">${(p.confidence || 0).toFixed(1)}%</span>
                    <span class="confidence-text">match score</span>
                </div>
                <span class="expand-icon">▼</span>
            </div>
            <div class="disease-card-body">
                <p style="color:var(--gray-500);margin-bottom:var(--space-5);line-height:1.7">${dis.info}</p>
                <div class="info-tabs" id="tabs-${i}">
                    <button class="info-tab active" data-tab="recs" onclick="tab(${i},'recs')">📋 Recommendations</button>
                    <button class="info-tab" data-tab="habits" onclick="tab(${i},'habits')">🌟 Daily Habits</button>
                    <button class="info-tab" data-tab="prevent" onclick="tab(${i},'prevent')">🛡️ Prevention</button>
                </div>
                <div class="tab-content active" id="recs-${i}">${renderRecs(dis.recs)}</div>
                <div class="tab-content" id="habits-${i}">${renderHabits(dis.habits)}</div>
                <div class="tab-content" id="prevent-${i}">${renderPrevent(dis.prevent)}</div>
            </div>
        </div>`;
    }).join('');
}

function renderRecs(recs) {
    if (!recs?.length) return '<p>No recommendations.</p>';
    return `<div class="recommendation-grid">${recs.map(r => `
        <div class="recommendation-card ${r.priority || ''}">
            <span class="recommendation-icon">${r.icon}</span>
            <h5 class="recommendation-title">${r.title}</h5>
            <p class="recommendation-text">${r.text}</p>
        </div>`).join('')}</div>`;
}

function renderHabits(habits) {
    if (!habits?.length) return '<p>No habits.</p>';
    return `<div class="habits-list">${habits.map(h => `
        <div class="habit-item">
            <div class="habit-icon-wrapper"><span class="habit-icon">${h.icon}</span></div>
            <div class="habit-content">
                <h5 class="habit-title">${h.title}</h5>
                <p class="habit-description">${h.desc}</p>
                <span class="habit-frequency"><span>🕐</span><span>${h.freq}</span></span>
            </div>
        </div>`).join('')}</div>`;
}

function renderPrevent(tips) {
    if (!tips?.length) return '<p>No tips.</p>';
    return `<div class="prevention-tips">${tips.map(t => `
        <div class="prevention-tip">
            <span class="prevention-icon">${t.icon}</span>
            <h5 class="prevention-title">${t.title}</h5>
            <p class="prevention-text">${t.text}</p>
        </div>`).join('')}</div>`;
}

// ═══════════════════════════════════════════════════════════════════════════════
// GLOBAL FUNCTIONS
// ═══════════════════════════════════════════════════════════════════════════════

window.toggle = id => document.getElementById(id)?.classList.toggle('expanded');

window.tab = (i, name) => {
    document.querySelectorAll(`#tabs-${i} .info-tab`).forEach(t => t.classList.toggle('active', t.dataset.tab === name));
    ['recs', 'habits', 'prevent'].forEach(n => {
        const el = document.getElementById(`${n}-${i}`);
        el && (el.classList.toggle('active', n === name));
    });
};

// ═══════════════════════════════════════════════════════════════════════════════
// ACTIONS
// ═══════════════════════════════════════════════════════════════════════════════

function initActions() {
    document.getElementById('retryBtn')?.addEventListener('click', () => State.file && analyze());
    document.getElementById('newAnalysis')?.addEventListener('click', reset);
    document.getElementById('downloadReport')?.addEventListener('click', downloadReport);
}

function reset() {
    const input = document.getElementById('imageInput');
    const area = document.getElementById('uploadArea');
    const preview = document.getElementById('imagePreview');
    const section = document.getElementById('analysisSection');

    State.file = null;
    State.analyzing = false;
    State.result = null;
    if (input) input.value = '';
    if (preview) preview.style.display = 'none';
    if (area) area.style.display = 'block';
    if (section) section.style.display = 'none';
}

function showError(msg) {
    const section = document.getElementById('analysisSection');
    const loading = document.getElementById('loading');
    const results = document.getElementById('results');
    const error = document.getElementById('error');
    const errMsg = document.getElementById('errorMessage');

    if (section) section.style.display = 'block';
    if (loading) loading.style.display = 'none';
    if (results) results.style.display = 'none';
    if (error) error.style.display = 'block';
    if (errMsg) errMsg.textContent = msg;
}

function downloadReport() {
    if (!State.result) return alert('No analysis to download');
    const { jsPDF } = window.jspdf;
    const doc = new jsPDF('p', 'mm', 'a4');
    const W = 210, M = 15, CW = W - 2 * M;
    let y = 0;

    const topPred = State.result.predictions[0];
    const d = getDisease(topPred?.label);
    const allPreds = State.result.predictions;
    const now = new Date();

    // Color palette
    const C = {
        primary: [14, 165, 233],
        dark: [15, 23, 42],
        text: [71, 85, 105],
        muted: [148, 163, 184],
        bg: [248, 250, 252],
        white: [255, 255, 255],
        green: [16, 185, 129],
        amber: [245, 158, 11],
        red: [239, 68, 68],
        teal: [20, 184, 166]
    };
    const sevCol = d.severity === 'healthy' ? C.green : d.severity === 'warning' ? C.amber : C.red;

    function needPage(h) { if (y + h > 280) { doc.addPage(); y = 20; } }

    function drawSection(title, color) {
        needPage(16);
        doc.setFillColor(...color);
        doc.rect(M, y, 3, 10, 'F');
        doc.setTextColor(...C.dark);
        doc.setFontSize(12);
        doc.setFont('helvetica', 'bold');
        doc.text(title, M + 7, y + 7);
        doc.setDrawColor(226, 232, 240);
        doc.setLineWidth(0.3);
        doc.line(M + 7, y + 10, M + CW, y + 10);
        y += 15;
    }

    // ═══ PAGE HEADER ═══
    doc.setFillColor(...C.primary);
    doc.rect(0, 0, W, 32, 'F');
    doc.setFillColor(...C.teal);
    doc.rect(0, 32, W, 2, 'F');

    doc.setTextColor(...C.white);
    doc.setFontSize(20);
    doc.setFont('helvetica', 'bold');
    doc.text('VisionAI', M, 14);
    doc.setFontSize(9);
    doc.setFont('helvetica', 'normal');
    doc.text('Eye Health Screening Report', M, 21);

    const dateStr = now.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
    const timeStr = now.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });
    const reportId = 'VR-' + Date.now().toString(36).toUpperCase();
    doc.setFontSize(8);
    doc.text(dateStr + '  •  ' + timeStr, W - M, 12, { align: 'right' });
    doc.text('ID: ' + reportId, W - M, 18, { align: 'right' });

    y = 42;

    // ═══ PRIMARY FINDING ═══
    doc.setFillColor(...C.bg);
    doc.roundedRect(M, y, CW, 30, 3, 3, 'F');
    doc.setDrawColor(...sevCol);
    doc.setLineWidth(0.6);
    doc.line(M, y, M, y + 30);

    // Severity badge
    doc.setFillColor(...sevCol);
    doc.roundedRect(M + 5, y + 4, 18, 6, 2, 2, 'F');
    doc.setTextColor(...C.white);
    doc.setFontSize(6);
    doc.setFont('helvetica', 'bold');
    doc.text(cap(d.severity).toUpperCase(), M + 14, y + 8.5, { align: 'center' });

    // Disease name
    doc.setTextColor(...C.dark);
    doc.setFontSize(14);
    doc.setFont('helvetica', 'bold');
    doc.text(d.name, M + 26, y + 9);

    // Match score
    doc.setTextColor(...C.text);
    doc.setFontSize(9);
    doc.setFont('helvetica', 'normal');
    doc.text('AI Match Score: ' + (topPred?.confidence || 0).toFixed(1) + '%', M + 5, y + 18);

    // Description
    doc.setFontSize(8);
    doc.setTextColor(...C.muted);
    const descLines = doc.splitTextToSize(d.desc, CW - 10);
    doc.text(descLines.slice(0, 2), M + 5, y + 24);

    y += 36;

    // ═══ ANALYSIS RESULTS TABLE ═══
    drawSection('Analysis Results', C.primary);

    // Column positions (fixed alignment)
    const col = { num: M + 3, name: M + 10, bar: M + 80, pct: M + 125, badge: M + 138 };

    // Table header
    doc.setFillColor(...C.primary);
    doc.roundedRect(M, y, CW, 8, 1.5, 1.5, 'F');
    doc.setTextColor(...C.white);
    doc.setFontSize(7);
    doc.setFont('helvetica', 'bold');
    doc.text('#', col.num, y + 5.5);
    doc.text('Condition', col.name, y + 5.5);
    doc.text('Match Score', col.bar, y + 5.5);
    doc.text('%', col.pct, y + 5.5);
    doc.text('Status', col.badge + 5, y + 5.5, { align: 'center' });
    y += 10;

    allPreds.forEach((p, i) => {
        needPage(9);
        const rd = getDisease(p.label);
        const sc = rd.severity === 'healthy' ? C.green : rd.severity === 'warning' ? C.amber : C.red;

        // Alternating row bg
        if (i % 2 === 0) {
            doc.setFillColor(248, 250, 252);
            doc.rect(M, y - 3, CW, 8, 'F');
        }

        // Row number
        doc.setTextColor(...C.muted);
        doc.setFontSize(8);
        doc.setFont('helvetica', 'normal');
        doc.text(String(i + 1), col.num, y + 2);

        // Condition name
        doc.setTextColor(...C.dark);
        doc.setFont('helvetica', 'bold');
        doc.text(rd.name.length > 28 ? rd.name.substring(0, 26) + '…' : rd.name, col.name, y + 2);

        // Progress bar background
        const barW = 42, barH = 3.5;
        doc.setFillColor(226, 232, 240);
        doc.roundedRect(col.bar, y - 0.5, barW, barH, 1, 1, 'F');

        // Progress bar fill
        doc.setFillColor(...sc);
        const fillW = Math.max(barW * (p.confidence / 100), 1.5);
        doc.roundedRect(col.bar, y - 0.5, fillW, barH, 1, 1, 'F');

        // Percentage text
        doc.setTextColor(...C.text);
        doc.setFont('helvetica', 'normal');
        doc.setFontSize(8);
        doc.text(p.confidence.toFixed(1) + '%', col.pct, y + 2);

        // Status badge
        doc.setFillColor(...sc);
        doc.roundedRect(col.badge, y - 2, 22, 6, 2, 2, 'F');
        doc.setTextColor(...C.white);
        doc.setFontSize(5.5);
        doc.setFont('helvetica', 'bold');
        doc.text(cap(rd.severity).toUpperCase(), col.badge + 11, y + 1.5, { align: 'center' });

        y += 8;
    });
    y += 8;

    // ═══ DETAILED ANALYSIS ═══
    drawSection('Detailed Analysis', C.teal);
    doc.setTextColor(...C.text);
    doc.setFontSize(9);
    doc.setFont('helvetica', 'normal');
    const infoLines = doc.splitTextToSize(d.info, CW - 6);
    needPage(infoLines.length * 4.5 + 4);
    doc.text(infoLines, M + 3, y);
    y += infoLines.length * 4.5 + 6;

    // ═══ RECOMMENDATIONS ═══
    if (d.recs && d.recs.length > 0) {
        drawSection('Recommendations', C.amber);
        d.recs.forEach((r, i) => {
            needPage(18);
            // Card background
            doc.setFillColor(255, 251, 235);
            doc.roundedRect(M, y - 2, CW, 15, 2, 2, 'F');

            // Number circle
            doc.setFillColor(...C.amber);
            doc.circle(M + 6, y + 3, 3, 'F');
            doc.setTextColor(...C.white);
            doc.setFontSize(7);
            doc.setFont('helvetica', 'bold');
            doc.text(String(i + 1), M + 6, y + 4.5, { align: 'center' });

            // Title
            doc.setTextColor(...C.dark);
            doc.setFontSize(10);
            doc.setFont('helvetica', 'bold');
            doc.text(r.title, M + 13, y + 4);

            // Description
            doc.setTextColor(...C.text);
            doc.setFontSize(8);
            doc.setFont('helvetica', 'normal');
            const recLines = doc.splitTextToSize(r.text, CW - 18);
            doc.text(recLines.slice(0, 1), M + 13, y + 10);

            y += 18;
        });
    }

    // ═══ DAILY HABITS ═══
    if (d.habits && d.habits.length > 0) {
        drawSection('Daily Habits', C.green);
        d.habits.forEach((h) => {
            needPage(14);
            doc.setFillColor(236, 253, 245);
            doc.roundedRect(M, y - 2, CW, 12, 2, 2, 'F');

            doc.setFillColor(...C.green);
            doc.circle(M + 5, y + 3, 1.5, 'F');

            doc.setTextColor(...C.dark);
            doc.setFontSize(9);
            doc.setFont('helvetica', 'bold');
            doc.text(h.title, M + 10, y + 3);

            doc.setTextColor(...C.muted);
            doc.setFontSize(7);
            doc.setFont('helvetica', 'normal');
            doc.text(h.freq, M + CW - 5, y + 3, { align: 'right' });

            doc.setTextColor(...C.text);
            doc.setFontSize(8);
            doc.text(h.desc, M + 10, y + 8);

            y += 14;
        });
    }

    // ═══ PREVENTION TIPS ═══
    if (d.prevent && d.prevent.length > 0) {
        drawSection('Prevention Tips', C.primary);
        d.prevent.forEach((p) => {
            needPage(12);
            doc.setTextColor(...C.primary);
            doc.setFontSize(9);
            doc.setFont('helvetica', 'bold');
            doc.text('▸', M + 3, y + 2);
            doc.setTextColor(...C.dark);
            doc.text(p.title, M + 9, y + 2);
            doc.setTextColor(...C.text);
            doc.setFontSize(8);
            doc.setFont('helvetica', 'normal');
            const tipLines = doc.splitTextToSize(p.text, CW - 12);
            doc.text(tipLines.slice(0, 1), M + 9, y + 7);
            y += 12;
        });
    }

    // ═══ MEDICAL DISCLAIMER ═══
    needPage(30);
    y += 5;
    doc.setFillColor(254, 243, 199);
    doc.roundedRect(M, y, CW, 24, 3, 3, 'F');
    doc.setDrawColor(...C.amber);
    doc.setLineWidth(0.4);
    doc.roundedRect(M, y, CW, 24, 3, 3, 'S');

    doc.setTextColor(146, 64, 14);
    doc.setFontSize(8);
    doc.setFont('helvetica', 'bold');
    doc.text('⚠  EDUCATIONAL DEMONSTRATION DISCLAIMER', M + CW / 2, y + 6, { align: 'center' });
    doc.setFontSize(7);
    doc.setFont('helvetica', 'normal');
    const disc = 'This screening tool is powered by an artificial intelligence model intended strictly for educational and research demonstration purposes. It does not provide medical advice, formal diagnosis, or treatment plans. Always consult a licensed ophthalmologist or healthcare provider for clinical evaluation. Do not disregard professional medical advice or delay seeking it because of results from this screening tool. For emergencies, contact your local emergency services immediately.';
    doc.text(doc.splitTextToSize(disc, CW - 14), M + 7, y + 12);

    // ═══ FOOTER ON EVERY PAGE ═══
    const totalPages = doc.internal.getNumberOfPages();
    for (let pg = 1; pg <= totalPages; pg++) {
        doc.setPage(pg);
        const pH = doc.internal.pageSize.height;
        doc.setFillColor(...C.primary);
        doc.rect(0, pH - 10, W, 10, 'F');
        doc.setTextColor(...C.white);
        doc.setFontSize(7);
        doc.setFont('helvetica', 'normal');
        doc.text('Powered by VisionAI Eye Hospital  |  AI-Powered Retinal Screening', W / 2, pH - 4, { align: 'center' });
        doc.text('Page ' + pg + ' of ' + totalPages, W - M, pH - 4, { align: 'right' });
    }

    doc.save('VisionAI_Report_' + now.toISOString().split('T')[0] + '.pdf');
}

// ═══════════════════════════════════════════════════════════════════════════════
// UTILITIES
// ═══════════════════════════════════════════════════════════════════════════════

function getDisease(label) {
    const norm = (label || '').toLowerCase().replace(/[_\s-]+/g, '_');
    const map = {
        // Diabetic Retinopathy variants
        no_dr: 'No_DR', mild: 'Mild', mild_dr: 'Mild',
        moderate: 'Moderate', moderate_dr: 'Moderate',
        severe: 'Severe', severe_dr: 'Severe',
        proliferative_dr: 'Proliferative_DR', proliferative: 'Proliferative_DR',
        // Healthy
        healthy: 'Healthy_Retina', normal: 'Healthy_Retina', healthy_retina: 'Healthy_Retina',
        // New model labels
        glaucoma: 'Glaucoma',
        amd: 'AMD', age_related_macular_degeneration: 'AMD', macular_degeneration: 'AMD',
        cataract: 'Cataract', cataracts: 'Cataract',
        hypertension: 'Hypertension', hypertensive_retinopathy: 'Hypertension',
        diabetes: 'Diabetes', diabetic_retinopathy: 'Diabetes', dr: 'Diabetes',
        other: 'Other', unknown: 'Other'
    };
    const key = map[norm] || label;
    return DB[key] || { ...DB.default, name: label.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()) };
}

const cap = s => s.charAt(0).toUpperCase() + s.slice(1);

function darken(hex, pct) {
    const n = parseInt(hex.replace('#', ''), 16);
    const a = Math.round(2.55 * -pct);
    const R = Math.max(0, Math.min(255, (n >> 16) + a));
    const G = Math.max(0, Math.min(255, (n >> 8 & 0xFF) + a));
    const B = Math.max(0, Math.min(255, (n & 0xFF) + a));
    return `#${(0x1000000 + R * 0x10000 + G * 0x100 + B).toString(16).slice(1)}`;
}
