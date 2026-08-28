"""Rank Taiwanese universities, departments and application groups by difficulty.

Covers both admission systems:
  - 一般大學 via 分發入學, 繁星推薦 and 個人申請
  - 科技大學 via 四技二專聯合登記分發 (統測), from tech-cutoffs.tsv

UAC cutoffs are converted to an equal-subject quantile coordinate from CEEC's
marginal score distributions. It is not the percentile of a weighted total;
the published cutoff lacks its subject-score vector. 術科 rows preserve their
old within-year position as a calibrated fallback.

The paths use different exams and populations, so their raw scores are not
comparable. A weighted, missing-data one-component model jointly calibrates the
matched department-years: the same department awarding the same degree, with no
assumption about relative ability of the 高中 and 高職 pools. Each row then maps
its own cutoff onto that common coordinate.

Scores average all available rank evidence (107-115) within each admission path,
then average paths by their annual admitted seats. Official totals report missing
coverage but do not affect scores. Entities that closed or merged remain in the
output, with `last_year` saying when they were last seen.
"""

import collections
import difflib
import os

from lib import deptname, tsvio
from lib.english import english_names
from lib.paths import data_path, ranking_path
from rank import ceec_score, gender

PATHS = ("uac", "tech", "star", "star_eight", "apply")
SOURCES = {"uac": "uac-cutoffs.tsv", "tech": "tech-cutoffs.tsv"}
ADMISSION_TOTALS = "admission-totals.tsv"
# The 學測 routes into 一般大學, each its own exam field. `system` stays the kind
# of institution; `path` is how the seat was won.
EXTRA = {
    "star": "star-cutoffs.tsv",
    "star_eight": "star-cutoffs.tsv",
    "apply": "apply-cutoffs.tsv",
}
# Paths with an externally defined percentile. Re-ranking them against the
# collected rows would replace their reported value with a partial-sample rank.
ABSOLUTE = {"apply", "star", "star_eight"}
# A 篩選 bar this much of the cohort clears did not screen anyone out.
NON_BINDING = 0.95
OCR_MATCH = 0.80
OCR_MARGIN = 0.15
COMPONENT_ITERATIONS = 30
COMPONENT_TOLERANCE = 1e-6
XUECE_STEM = frozenset(("數學", "數學A", "數學B", "自然"))


def identify_department(row):
    """Preserve the source 系組 name, then attach its reporting department."""
    row["application_group"] = row["dept"].strip()
    row["dept"] = deptname.normalize(row["application_group"])


def xuece_cluster(label, families=3):
    """Coarsen a 學測 subset into language, social, and STEM families."""
    subjects = ceec_score.split_subjects(label)
    if not subjects:
        return None
    if families == 1:
        return "all"
    if set(subjects) & XUECE_STEM:
        return "stem"
    if families == 3 and "社會" in subjects:
        return "social"
    return "language"


def star_gate_families(cohort, year, gates):
    """Strictest binding gate in each of the three 學測 subject families."""
    out = {}
    for subject, top in cohort.binding_gates(year, gates):
        family = xuece_cluster(subject)
        if family is not None:
            out[family] = max(out.get(family, 0.0), 100.0 * (1.0 - top))
    return out


def load(system, distributions=None):
    """Rows for one admission system.

    Department names are normalised, so the several 組 a department admits
    through arrive under one name.
    """
    for row in tsvio.read_rows(data_path(SOURCES[system])):
        row["system"] = system
        row["path"] = system
        identify_department(row)
        row["seats"] = int(row["seats"])
        row["norm"] = float(row["norm"])
        row["basis"] = row["norm"]
        if distributions is not None:
            percentile = (
                distributions.formula_percentile(
                    row["year"], row["subjects"], row["cutoff"]
                )
                if system == "uac"
                else distributions.tongce_percentile(
                    row["year"], row["subjects"], row["cutoff"], row["group"]
                )
            )
            if percentile is not None:
                row["ceec_percentile"] = percentile
                if system == "uac":
                    row["basis"] = percentile
        yield row


def load_star(group="one2seven", cohort=None):
    """繁星推薦 rows, ordered so that bigger is better.

    `gpa` is the marginal admittee's rank inside their own school, where 1%
    beats 17%, so it is negated to match every other path. 第八類學群 publishes
    a pre-interview screen, so it keeps its own path and uses its quota rather
    than its screened count as the aggregation weight.
    """
    for row in tsvio.read_rows(data_path(EXTRA["star"])):
        admitted = int(row["admitted"] or 0)
        if row["group"] != group or not row["gpa"] or not admitted:
            continue
        row["system"] = "uac"
        row["path"] = "star" if group == "one2seven" else "star_eight"
        row["school"] = row["college"]
        identify_department(row)
        row["screened"] = admitted
        row["seats"] = int(row["quota"] or 0) if group == "eight" else admitted
        if not row["seats"]:
            continue
        row["norm"] = -float(row["gpa"])
        row["class_pct"] = 100.0 - float(row["gpa"])
        row["xuece_gates"] = (
            star_gate_families(cohort, row["year"], row["gates"])
            if cohort is not None else {}
        )
        # Every subject's own bar, kept apart. A department asking 頂標 of four
        # subjects wants far more than the strictest one of them says.
        row["xuece_tops"] = (
            [top for _, top in cohort.binding_gates(row["year"], row["gates"])]
            if cohort is not None else []
        )
        # Class rank is national only under the equal-school assumption. The
        # jointly fitted component also uses the family-specific 學測 gates.
        row["basis"] = row["class_pct"]
        yield row


def load_apply(cohort):
    """個人申請 rows, scored as a share of the national 學測 cohort.

    A `norm` above 1 is impossible and means a subject was lost from a composite
    label, and a blank 校系名稱 cannot be joined to a department.

    `basis` reads the published 篩選 bar against the 學測 級分 distribution: the
    share of everyone who sat the exam who cleared it. A bar almost nobody fails
    says only that this 篩選順序 was not what bound, so those rows are dropped.
    """
    for row in tsvio.read_rows(data_path(EXTRA["apply"])):
        if not row["norm"] or not row["dept"].strip():
            continue
        norm = float(row["norm"])
        admitted = int(row["admitted"] or 0)
        if norm > 1 or not admitted:
            continue
        top = cohort.top_fraction(row["year"], row["cut_label"], row["cut_level"])
        if top is None or top >= NON_BINDING:
            continue
        row["system"], row["path"] = "uac", "apply"
        row["school"] = row["college"]
        identify_department(row)
        row["xuece_cluster"] = xuece_cluster(row["cut_label"])
        row["seats"] = admitted
        row["norm"] = norm
        row["basis"] = 100.0 * (1.0 - top)
        yield row


def load_admission_totals():
    """Official admitted seats by year and path, including unparsed schools."""
    totals = {}
    for row in tsvio.read_rows(data_path(ADMISSION_TOTALS)):
        key = (row["year"], row["path"])
        if key in totals:
            raise ValueError(f"duplicate admission total for {key}")
        totals[key] = int(row["admitted"])
    return totals


def joinable(rows, known):
    """Keep only rows whose department also admits through 分發入學 that year.

    The same department may spell ``系`` or ``學系`` across admission paths;
    compare the reporting key rather than that superficial spelling. 個申's
    department cells are OCR, so an unambiguous close spelling can be repaired
    against the departments its own school admits through 分發. Other paths are
    text sources and must match exactly.
    """
    by_school = collections.defaultdict(dict)
    for year, school, dept in known:
        by_school[(year, school)][deptname.key(dept)] = dept
    out = []
    for row in rows:
        candidates = by_school[(row["year"], row["school"])]
        key = deptname.key(row["dept"])
        if key in candidates:
            row["dept"] = candidates[key]
            out.append(row)
            continue
        if row.get("path") != "apply":
            continue
        matched = ocr_department(row["dept"], candidates)
        if matched:
            row["dept"] = matched
            out.append(row)
    return out


def ocr_department(source, candidates):
    """Return an unambiguous OCR repair from a school's known departments."""
    source = chinese_chars(source)
    if not source:
        return None
    scored = sorted(
        (
            difflib.SequenceMatcher(None, source, chinese_chars(value)).ratio(),
            value,
        )
        for value in candidates.values()
    )
    if not scored:
        return None
    best, value = scored[-1]
    next_best = scored[-2][0] if len(scored) > 1 else 0.0
    return value if best >= OCR_MATCH and best - next_best >= OCR_MARGIN else None


def chinese_chars(value):
    """CJK department text, without OCR punctuation and Latin debris."""
    return "".join(char for char in value if "\u4e00" <= char <= "\u9fff")


def unify_spelling(rows):
    """Give each department one name, the spelling that admitted the most students."""
    seats = collections.defaultdict(collections.Counter)
    for row in rows:
        seats[(row["school"], deptname.key(row["dept"]))][row["dept"]] += row["seats"]
    names = {k: c.most_common(1)[0][0] for k, c in seats.items()}
    for row in rows:
        row["dept"] = names[(row["school"], deptname.key(row["dept"]))]


def wmean(rows, field):
    seats = sum(r["seats"] for r in rows)
    return sum(r[field] * r["seats"] for r in rows) / seats if seats else 0.0


def curve(rows, source, target, key):
    """Set `target` to where `source` falls among the seats it competes with, 0-100.

    Keying on year and admission path curves each route against its own field,
    which makes the bridge fit on comparable scales. Keying on year alone
    curves the merged pool once both systems are on one axis. Rows sharing a
    value share the midpoint of the seats they span.
    """
    groups = collections.defaultdict(list)
    for row in rows:
        groups[key(row)].append(row)
    for group in groups.values():
        values, percentiles = ceec_score.weighted_midpoints(group, source)
        percentile_of = dict(zip(values, percentiles))
        for row in group:
            row[target] = 100.0 * percentile_of[row[source]]


def coverage_gaps(rows, totals):
    """Return unscored official seats by year and by (year, path).

    Only rows that survive parsing and joining are `observed`. Thus a rejected
    row remains visible in the coverage audit without supplying rank evidence.
    """
    observed = collections.Counter()
    for row in rows:
        observed[(row["year"], row["path"])] += row["seats"]
    audited_years = {year for year, _ in totals}
    uncovered = {key for key in set(observed) - set(totals)
                 if key[0] in audited_years}
    if uncovered:
        raise ValueError(f"missing official admission totals for {sorted(uncovered)}")

    residual = {}
    by_year = collections.Counter()
    for key, admitted in totals.items():
        missing = admitted - observed[key]
        if missing < 0:
            raise ValueError(
                f"ranked seats exceed official total for {key}: "
                f"{observed[key]} > {admitted}"
            )
        residual[key] = missing
        by_year[key[0]] += missing
    return dict(by_year), residual


def by_dept(rows, field="pct"):
    """Collapse rows to (`field`, seats) per (year, school, department)."""
    groups = collections.defaultdict(list)
    for row in rows:
        groups[(row["year"], row["school"], row["dept"])].append(row)
    out = {}
    for key, group in groups.items():
        seats = sum(row["seats"] for row in group)
        if seats:
            out[key] = (wmean(group, field), seats)
    return out


def component_group(variable):
    """Each 學測 family keeps an intercept while sharing its path's slope."""
    if variable.startswith("apply:"):
        return "apply"
    if variable.startswith("star:gate:"):
        return "star:gate"
    return variable


def source_group(variable):
    """Measurements that arrive from one admission path leave validation together."""
    return "star" if variable.startswith("star:") else component_group(variable)


def matched_component_observations(observations):
    """Keep only department-years that link at least two admission paths.

    A one-path department-year locates itself exactly on that path's line. It
    adds no cross-path information, so including it would inflate fit quality.
    """
    groups = collections.defaultdict(list)
    for observation in observations:
        groups[observation[0]].append(observation)
    return [
        observation
        for values in groups.values()
        if len({source_group(value[1]) for value in values}) > 1
        for observation in values
    ]


class ComponentModel:
    """One latent selectivity coordinate with a line for each measurement."""

    def __init__(self, intercepts, slopes, scores, scales):
        self.intercepts = intercepts
        self.slopes = slopes
        self.scores = scores
        self.scales = scales

    def predict(self, variable, value):
        """Map one observed cutoff onto the latent coordinate."""
        return (value - self.intercepts[variable]) / self.slopes[component_group(variable)]

    def reconstruct(self, variable, score):
        """Map the latent coordinate back into one measurement's units."""
        return self.intercepts[variable] + self.slopes[component_group(variable)] * score

    def combine(self, measurements):
        """Combine the independent measurements published for one row."""
        numerator = denominator = 0.0
        for variable, value in measurements:
            slope = self.slopes[component_group(variable)]
            precision = slope ** 2 / self.scales[variable] ** 2
            numerator += precision * self.predict(variable, value)
            denominator += precision
        return numerator / denominator if denominator else 0.0


def by_dept_star_inputs(rows):
    """Seat-average class rank and each available 繁星 gate family."""
    groups = collections.defaultdict(list)
    for row in rows:
        groups[(row["year"], row["school"], row["dept"])].append(row)
    out = {}
    for key, group in groups.items():
        seats = sum(row["seats"] for row in group)
        if not seats:
            continue
        values = {"star:class": wmean(group, "class_pct")}
        for family in ("language", "social", "stem"):
            family_rows = [row for row in group if family in row["xuece_gates"]]
            if family_rows:
                total = sum(row["seats"] for row in family_rows)
                values[f"star:gate:{family}"] = sum(
                    row["seats"] * row["xuece_gates"][family] for row in family_rows
                ) / total
        out[key] = (values, seats)
    return out


def by_dept_xuece(rows, families=3):
    """One 學測 score and subject family per department-year.

    Almost every department-year has one family. For the small mixed remainder,
    take the family carrying the most reported admits.
    """
    groups = collections.defaultdict(list)
    for row in rows:
        groups[(row["year"], row["school"], row["dept"])].append(row)
    out = {}
    for key, group in groups.items():
        seats = sum(row["seats"] for row in group)
        clusters = collections.Counter(
            xuece_cluster(row["cut_label"], families) for row in group
        )
        cluster = clusters.most_common(1)[0][0] if clusters else None
        if seats and cluster is not None:
            out[key] = ((wmean(group, "pct"), cluster), seats)
    return out


def add_component_source(out, source, variable):
    """Append one collapsed measurement type to component observations."""
    for key, (value, seats) in source.items():
        out.append((key, variable, value, seats))


def component_observations(uac_rows, tech_rows, extra):
    """Measurements joined by department-year for the one-component fit."""
    out = []
    add_component_source(out, by_dept(uac_rows), "uac")
    add_component_source(out, by_dept(tech_rows), "tech")
    stars = by_dept_star_inputs(extra["star"] + extra["star_eight"])
    for key, (values, seats) in stars.items():
        out += [(key, variable, value, seats) for variable, value in values.items()]
    for key, ((value, family), seats) in by_dept_xuece(extra["apply"]).items():
        out.append((key, f"apply:{family}", value, seats))
    return out


def component_weights(observations):
    """Standardize types, give each one equal influence, and retain seat weights."""
    totals = collections.Counter()
    values = collections.defaultdict(list)
    for _, variable, _, seats in observations:
        totals[variable] += seats
    for _, variable, value, seats in observations:
        values[variable].append((value, seats))
    scales = {}
    for variable, pairs in values.items():
        mean = weighted_mean(pairs)
        variance = weighted_mean([((value - mean) ** 2, seats) for value, seats in pairs])
        scales[variable] = max(variance, 1e-9)
    return [
        (key, variable, value, seats / totals[variable] / scales[variable])
        for key, variable, value, seats in observations
    ]


def weighted_mean(values):
    """Mean of (value, weight) pairs, returning zero for an empty sequence."""
    total = sum(weight for _, weight in values)
    return sum(value * weight for value, weight in values) / total if total else 0.0


def normalise_component(scores, weights):
    """Fix the arbitrary origin and scale of the latent coordinate."""
    pairs = [(value, weights[key]) for key, value in scores.items()]
    mean = weighted_mean(pairs)
    variance = weighted_mean([((value - mean) ** 2, weight) for value, weight in pairs])
    scale = variance ** 0.5
    if not scale:
        raise ValueError("component has no variation")
    return {key: (value - mean) / scale for key, value in scores.items()}


def component_scales(observations):
    """Weighted raw standard deviation of each measurement type."""
    grouped = collections.defaultdict(list)
    for _, variable, value, weight in observations:
        grouped[variable].append((value, weight))
    out = {}
    for variable, values in grouped.items():
        mean = weighted_mean(values)
        variance = weighted_mean([((value - mean) ** 2, weight) for value, weight in values])
        out[variable] = max(variance ** 0.5, 1e-9)
    return out


def initial_component_scores(observations, entity_weights):
    """Start the alternating fit from the average within-variable z-score."""
    grouped = collections.defaultdict(list)
    for key, variable, value, weight in observations:
        grouped[variable].append((key, value, weight))
    means = {
        variable: weighted_mean([(value, weight) for _, value, weight in values])
        for variable, values in grouped.items()
    }
    scales = component_scales(observations)
    sums = collections.defaultdict(lambda: [0.0, 0.0])
    for key, variable, value, weight in observations:
        sums[key][0] += weight * (value - means[variable]) / scales[variable]
        sums[key][1] += weight
    scores = {key: total / weight for key, (total, weight) in sums.items()}
    return normalise_component(scores, entity_weights)


def component_loadings(observations, scores):
    """Fit each intercept and each (possibly shared) measurement slope."""
    grouped = collections.defaultdict(list)
    for key, variable, value, weight in observations:
        grouped[variable].append((key, value, weight))
    means = {}
    for variable, values in grouped.items():
        means[variable] = (
            weighted_mean([(value, weight) for _, value, weight in values]),
            weighted_mean([(scores[key], weight) for key, _, weight in values]),
        )
    numerators = collections.Counter()
    denominators = collections.Counter()
    for key, variable, value, weight in observations:
        mean_value, mean_score = means[variable]
        group = component_group(variable)
        numerators[group] += weight * (value - mean_value) * (scores[key] - mean_score)
        denominators[group] += weight * (scores[key] - mean_score) ** 2
    slopes = {group: numerators[group] / denominators[group]
              for group in numerators if denominators[group]}
    if not slopes or min(slopes.values()) <= 0:
        raise ValueError("component requires positive correlations")
    intercepts = {
        variable: mean_value - slopes[component_group(variable)] * mean_score
        for variable, (mean_value, mean_score) in means.items()
    }
    return intercepts, slopes


def component_scores(observations, intercepts, slopes):
    """Least-squares latent score for each department-year."""
    totals = collections.defaultdict(lambda: [0.0, 0.0])
    for key, variable, value, weight in observations:
        slope = slopes[component_group(variable)]
        totals[key][0] += weight * slope * (value - intercepts[variable])
        totals[key][1] += weight * slope ** 2
    return {key: total / weight for key, (total, weight) in totals.items() if weight}


def component_stats(observations, model):
    """Explained within-measurement variance, with types weighted equally."""
    total = residual = 0.0
    means = collections.defaultdict(list)
    for _, variable, value, weight in observations:
        means[variable].append((value, weight))
    means = {variable: weighted_mean(values) for variable, values in means.items()}
    for key, variable, value, weight in observations:
        scale = model.scales[variable] ** 2
        total += weight * (value - means[variable]) ** 2 / scale
        residual += weight * (value - model.reconstruct(variable, model.scores[key])) ** 2 / scale
    return 1 - residual / total if total else 0.0


def fit_component(observations):
    """Fit the weighted, missing-data first component by alternating least squares."""
    if not observations:
        raise ValueError("no measurements for component fit")
    observations = component_weights(observations)
    entity_weights = collections.Counter({key: 1.0 for key, _, _, _ in observations})
    scores = initial_component_scores(observations, entity_weights)
    for iteration in range(1, COMPONENT_ITERATIONS + 1):
        intercepts, slopes = component_loadings(observations, scores)
        updated = normalise_component(
            component_scores(observations, intercepts, slopes), entity_weights
        )
        difference = weighted_mean([
            ((updated[key] - scores[key]) ** 2, entity_weights[key]) for key in scores
        ]) ** 0.5
        scores = updated
        if difference < COMPONENT_TOLERANCE:
            break
    intercepts, slopes = component_loadings(observations, scores)
    model = ComponentModel(intercepts, slopes, scores, component_scales(observations))
    variables = sorted({variable for _, variable, _, _ in observations})
    return model, {
        "model": "one component",
        "iterations": iteration,
        "observations": len(observations),
        "entities": len(scores),
        "variables": variables,
        "r2": component_stats(observations, model),
    }


def component_validation_error(observations):
    """Leave universities out, then compare every held path with its companions."""
    schools = sorted({key[1] for key, _, _, _ in observations})
    if len(schools) < 2:
        return 0.0
    fold = {school: index % min(5, len(schools)) for index, school in enumerate(schools)}
    by_key = collections.defaultdict(list)
    for observation in observations:
        by_key[observation[0]].append(observation)
    error = weight = 0.0
    for held in set(fold.values()):
        train = [point for point in observations if fold[point[0][1]] != held]
        model, _ = fit_component(train)
        for key, points in by_key.items():
            if fold[key[1]] != held:
                continue
            sources = collections.defaultdict(list)
            for _, variable, value, seats in points:
                sources[source_group(variable)].append((variable, value, seats))
            for source, held_points in sources.items():
                others = [
                    (variable, value)
                    for other_source, source_points in sources.items()
                    if other_source != source
                    for variable, value, _ in source_points
                ]
                if others:
                    held_measurements = [(variable, value) for variable, value, _ in held_points]
                    seats = sum(point[2] for point in held_points) / len(held_points)
                    error += seats * (model.combine(held_measurements) - model.combine(others)) ** 2
                    weight += seats
    return (error / weight) ** 0.5 if weight else 0.0


def set_component_scores(model, uac_rows, tech_rows, extra):
    """Map each published bar onto the jointly fitted component.

    Keep individual 分發 and 個申 application groups separate in the output.
    The fit uses department-year means only to link paths that describe the same
    degree in the same year.
    """
    for row in uac_rows:
        row["rank_basis"] = model.predict("uac", row["pct"])
    for row in tech_rows:
        row["rank_basis"] = model.predict("tech", row["pct"])
    for path in ("star", "star_eight"):
        for row in extra[path]:
            measurements = [("star:class", row["class_pct"])]
            measurements += [
                (f"star:gate:{family}", value)
                for family, value in row["xuece_gates"].items()
            ]
            row["rank_basis"] = model.combine(measurements)
    for row in extra["apply"]:
        row["rank_basis"] = model.predict(
            f"apply:{row['xuece_cluster']}", row["pct"]
        )


def aggregate(rows, key):
    """Average within admission path, then average paths by annual seats.

    Source coverage differs by path: 分發入學 has seven years while the
    current 繁星 and 個申 samples have two. Within a path, rows and years are
    weighted by admitted seats. Across paths, the weight is average annual seats,
    so the number of downloaded years is not itself a vote in the final score.
    """
    groups = collections.defaultdict(list)
    for row in rows:
        groups[key(row)].append(row)
    out = []
    for name, group in groups.items():
        path_groups = collections.defaultdict(list)
        for row in group:
            path_groups[row["path"]].append(row)
        paths, by_path = [], {}
        for path, path_group in path_groups.items():
            path_years = len({r["year"] for r in path_group})
            path_seats = sum(r["seats"] for r in path_group)
            if path_years and path_seats:
                score = wmean(path_group, "score")
                by_path[path] = score
                paths.append({"score": score, "seats": path_seats / path_years})
        seats_avg = sum(path["seats"] for path in paths)
        if not seats_avg:
            continue
        out.append(
            {
                "key": name,
                "score": wmean(paths, "score"),
                "years": len({r["year"] for r in group}),
                "last_year": max(r["year"] for r in group),
                "seats_avg": seats_avg,
                "by_path": by_path,
            }
        )
    return sorted(out, key=lambda d: -d["score"])


def write(path, header, ranked, counts, english):
    """Write a ranking with generated English labels and optional gender counts.

    `counts` maps a row key to (men, women); absent keys leave those cells blank.
    """
    matched = 0
    with open(path, "w", encoding="utf-8") as f:
        f.write("\t".join(header) + "\n")
        for i, d in enumerate(ranked, 1):
            fields = [str(i)]
            names = d["key"] if isinstance(d["key"], tuple) else (d["key"],)
            for name in names:
                fields += [name, english.get(name, "")]
            fields += [f"{d['score']:.2f}", str(d["years"]), str(d["last_year"])]
            fields += [f"{d['seats_avg']:.1f}"]
            fields += [f"{d['by_path'][p]:.2f}" if p in d["by_path"] else ""
                       for p in PATHS]
            found = counts(d["key"])
            if found and sum(found):
                men, women = found
                fields += [str(men), str(women), f"{women / (men + women):.3f}"]
                matched += 1
            else:
                fields += ["", "", ""]
            f.write("\t".join(fields) + "\n")
    print(f"{len(ranked):>5} rows -> {os.path.basename(path)}  ({matched} with gender)")


def build_rows(with_models=False):
    """Run the pipeline and return every row carrying its final `score`.

    Split out from main() so a diagnostic can read the per-path scores that the
    rankings then average away. `with_models` also returns the component model.
    """
    scores = data_path("ceec-scores.tsv")
    distributions = ceec_score.ScoreDistributions.load(
        scores, data_path("tongce-scores.tsv")
    )
    cohort = ceec_score.CohortPercentiles.load(scores)
    uac_rows = list(load("uac", distributions))
    tech_rows = list(load("tech", distributions))
    adjusted = sum("ceec_percentile" in row for row in uac_rows)
    fallbacks = ceec_score.calibrate_fallbacks(uac_rows)
    print(
        f"CEEC: adjusted {adjusted} of {len(uac_rows)} UAC rows;"
        f" calibrated {fallbacks} 術科 fallbacks"
    )
    read = sum("ceec_percentile" in row for row in tech_rows)
    print(f"統測: read {read} of {len(tech_rows)} 四技二專 rows against its takers")
    unify_spelling(uac_rows + tech_rows)
    known = {(r["year"], r["school"], r["dept"]) for r in uac_rows}
    extra = {}
    loaders = (
        ("star", lambda: load_star(cohort=cohort)),
        ("star_eight", lambda: load_star("eight", cohort)),
        ("apply", lambda: load_apply(cohort)),
    )
    for path, loader in loaders:
        got = list(loader())
        kept = joinable(got, known)
        extra[path] = kept
        print(f"{path}: {len(kept)} of {len(got)} rows join a 分發入學 department")

    rows = uac_rows + tech_rows + extra["star"] + extra["star_eight"] + extra["apply"]
    unify_spelling(rows)
    # Curving turns a value into a position among the seats collected alongside
    # it, which is what the incompletely collected paths must not have done to
    # them. Their basis is already national, so it carries straight through.
    curve([r for r in rows if r["path"] not in ABSOLUTE], "basis", "pct",
          lambda r: (r["year"], r["path"]))
    for row in rows:
        if row["path"] in ABSOLUTE:
            row["pct"] = row["basis"]

    observations = matched_component_observations(
        component_observations(uac_rows, tech_rows, extra)
    )
    component, stats = fit_component(observations)
    stats["cv_rmse"] = component_validation_error(observations)
    models = {"component": (component, stats)}
    print(
        f"component: R2={stats['r2']:.3f}  cross-source CV RMSE="
        f"{stats['cv_rmse']:.3f} SD  {stats['observations']} observations"
        f"  ({stats['entities']} department-years, {len(stats['variables'])} variables,"
        f" {stats['iterations']} iterations)"
    )
    set_component_scores(component, uac_rows, tech_rows, extra)

    # Report missing coverage without assigning those seats a rank.
    # 第八類 is part of the official 繁星 total but publishes a screen count,
    # not an admission count, so it has no independent coverage total.
    covered_rows = [row for row in rows if row["path"] != "star_eight"]
    gaps, residual = coverage_gaps(covered_rows, load_admission_totals())
    curve(rows, "rank_basis", "score", lambda r: r["year"])
    by_path = collections.Counter()
    for (_, path), missing in residual.items():
        by_path[path] += missing
    print(
        "coverage gaps: "
        + ", ".join(f"{year}={gaps[year]:,}" for year in sorted(gaps))
    )
    print(
        "coverage gaps by path: "
        + ", ".join(
            f"{path}={by_path[path]:,}"
            for path in ("uac", "tech", "star", "apply", "tech_select")
        )
    )
    return (rows, models) if with_models else rows


def main():
    os.makedirs(ranking_path(), exist_ok=True)
    rows = build_rows()
    uac_rows = [r for r in rows if r["path"] == "uac"]
    tech_rows = [r for r in rows if r["path"] == "tech"]
    tail = ["score", "years", "last_year", "seats_avg"] + list(PATHS)
    tail += ["men", "women", "pct_women"]
    by_dept_counts = gender.load()
    by_school_counts = gender.school_totals(by_dept_counts)
    names = {row[field] for row in rows
             for field in ("school", "dept", "application_group") if row.get(field)}
    english = english_names(names)
    write(
        ranking_path("rank-universities.tsv"),
        ["rank", "school", "school_en"] + tail,
        aggregate(rows, lambda r: r["school"]),
        lambda school: by_school_counts.get(school),
        english,
    )
    write(
        ranking_path("rank-departments.tsv"),
        ["rank", "school", "school_en", "dept", "dept_en"] + tail,
        aggregate(rows, lambda r: (r["school"], r["dept"])),
        lambda key: gender.lookup(by_dept_counts, *key),
        english,
    )
    write(
        ranking_path("rank-application-groups.tsv"),
        [
            "rank",
            "school",
            "school_en",
            "dept",
            "dept_en",
            "application_group",
            "application_group_en",
        ]
        + tail,
        aggregate(
            uac_rows + tech_rows,
            lambda r: (r["school"], r["dept"], r["application_group"]),
        ),
        lambda key: None,
        english,
    )


if __name__ == "__main__":
    main()
