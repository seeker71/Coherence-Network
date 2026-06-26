import Foundation
import SatsangMacCore

#if canImport(HealthKit)
import HealthKit
#endif

enum WearableHealthImportError: Error, LocalizedError {
    case unavailable(String)
    case authorizationDenied
    case missingSampleType(String)

    var errorDescription: String? {
        switch self {
        case .unavailable(let reason):
            return reason
        case .authorizationDenied:
            return "Health access was not granted."
        case .missingSampleType(let identifier):
            return "HealthKit sample type is unavailable: \(identifier)."
        }
    }
}

final class WearableHealthImporter {
    static let defaultSourceHints = [
        "Oura",
        "Oz",
        "O2",
        "Wellue",
        "ViHealth",
        "oxygen",
        "oximeter",
    ]

    static func detectResourceDoors() -> [HostResourceDoor] {
        #if canImport(HealthKit) && os(iOS)
        let available = HKHealthStore.isHealthDataAvailable()
        return [
            HostResourceDoor(
                kind: "health-samples",
                state: available ? "available" : "unavailable",
                carrier: "ios-healthkit",
                detail: "explicit read authorization for wearable samples"
            )
        ]
        #else
        return [
            HostResourceDoor(
                kind: "health-samples",
                state: "unavailable",
                carrier: "healthkit-unavailable-on-this-host",
                detail: "iPhone HealthKit carrier required"
            )
        ]
        #endif
    }

    func importRecentSamples(daysBack: Int, sourceNameHints: [String]) async throws -> [TrustedHealthSample] {
        #if canImport(HealthKit) && os(iOS)
        guard HKHealthStore.isHealthDataAvailable() else {
            throw WearableHealthImportError.unavailable("Health data is not available on this device.")
        }
        let healthStore = HKHealthStore()
        let specs = Self.quantitySpecs()
        let categoryTypes = try Self.categoryTypes()
        var readTypes = Set<HKObjectType>()
        specs.forEach { readTypes.insert($0.type) }
        categoryTypes.forEach { readTypes.insert($0) }
        readTypes.insert(HKObjectType.workoutType())
        try await requestAuthorization(healthStore: healthStore, readTypes: readTypes)

        let end = Date()
        let start = Calendar.current.date(byAdding: .day, value: -max(daysBack, 1), to: end) ?? end
        let hints = sourceNameHints.map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }

        var samples: [TrustedHealthSample] = []
        for spec in specs {
            samples += try await fetchQuantitySamples(
                healthStore: healthStore,
                spec: spec,
                start: start,
                end: end,
                sourceNameHints: hints
            )
        }
        samples += try await fetchSleepSamples(
            healthStore: healthStore,
            start: start,
            end: end,
            sourceNameHints: hints
        )
        samples += try await fetchWorkoutSamples(
            healthStore: healthStore,
            start: start,
            end: end,
            sourceNameHints: hints
        )
        return samples.sorted { $0.endDate < $1.endDate }
        #else
        throw WearableHealthImportError.unavailable("HealthKit import is available only in the native iPhone carrier.")
        #endif
    }
}

#if canImport(HealthKit) && os(iOS)
private struct QuantitySpec {
    var identifier: HKQuantityTypeIdentifier
    var type: HKQuantityType
    var kind: String
    var unit: HKUnit
    var displayUnit: String
    var transform: @Sendable (Double) -> Double
}

private extension WearableHealthImporter {
    static func quantitySpecs() -> [QuantitySpec] {
        [
            quantitySpec(.heartRate, kind: "heart-rate", unit: HKUnit.count().unitDivided(by: .minute()), displayUnit: "count/min"),
            quantitySpec(.restingHeartRate, kind: "resting-heart-rate", unit: HKUnit.count().unitDivided(by: .minute()), displayUnit: "count/min"),
            quantitySpec(.heartRateVariabilitySDNN, kind: "hrv-sdnn", unit: HKUnit.secondUnit(with: .milli), displayUnit: "ms"),
            quantitySpec(.oxygenSaturation, kind: "spo2", unit: .percent(), displayUnit: "%", transform: { $0 <= 1.5 ? $0 * 100.0 : $0 }),
            quantitySpec(.respiratoryRate, kind: "respiratory-rate", unit: HKUnit.count().unitDivided(by: .minute()), displayUnit: "count/min"),
            quantitySpec(.stepCount, kind: "steps", unit: .count(), displayUnit: "count"),
            quantitySpec(.activeEnergyBurned, kind: "active-energy", unit: .kilocalorie(), displayUnit: "kcal"),
            quantitySpec(.bodyTemperature, kind: "body-temperature", unit: .degreeCelsius(), displayUnit: "degC"),
        ]
    }

    static func quantitySpec(
        _ identifier: HKQuantityTypeIdentifier,
        kind: String,
        unit: HKUnit,
        displayUnit: String,
        transform: @escaping @Sendable (Double) -> Double = { $0 }
    ) -> QuantitySpec {
        guard let type = HKObjectType.quantityType(forIdentifier: identifier) else {
            fatalError("Missing HealthKit quantity type \(identifier.rawValue)")
        }
        return QuantitySpec(
            identifier: identifier,
            type: type,
            kind: kind,
            unit: unit,
            displayUnit: displayUnit,
            transform: transform
        )
    }

    static func categoryTypes() throws -> [HKSampleType] {
        guard let sleep = HKObjectType.categoryType(forIdentifier: .sleepAnalysis) else {
            throw WearableHealthImportError.missingSampleType("sleepAnalysis")
        }
        return [sleep]
    }

    func requestAuthorization(healthStore: HKHealthStore, readTypes: Set<HKObjectType>) async throws {
        try await withCheckedThrowingContinuation { continuation in
            healthStore.requestAuthorization(toShare: Set<HKSampleType>(), read: readTypes) { success, error in
                if let error {
                    continuation.resume(throwing: error)
                    return
                }
                guard success else {
                    continuation.resume(throwing: WearableHealthImportError.authorizationDenied)
                    return
                }
                continuation.resume(returning: ())
            }
        }
    }

    func fetchQuantitySamples(
        healthStore: HKHealthStore,
        spec: QuantitySpec,
        start: Date,
        end: Date,
        sourceNameHints: [String]
    ) async throws -> [TrustedHealthSample] {
        let predicate = HKQuery.predicateForSamples(withStart: start, end: end)
        let sort = NSSortDescriptor(key: HKSampleSortIdentifierEndDate, ascending: false)
        return try await withCheckedThrowingContinuation { continuation in
            let query = HKSampleQuery(
                sampleType: spec.type,
                predicate: predicate,
                limit: 500,
                sortDescriptors: [sort]
            ) { _, rawSamples, error in
                if let error {
                    continuation.resume(throwing: error)
                    return
                }
                let rows = (rawSamples as? [HKQuantitySample] ?? [])
                    .filter { Self.matchesSource($0, hints: sourceNameHints) }
                    .map { sample in
                        Self.healthSample(
                            sample: sample,
                            kind: spec.kind,
                            value: spec.transform(sample.quantity.doubleValue(for: spec.unit)),
                            unit: spec.displayUnit
                        )
                    }
                continuation.resume(returning: rows)
            }
            healthStore.execute(query)
        }
    }

    func fetchSleepSamples(
        healthStore: HKHealthStore,
        start: Date,
        end: Date,
        sourceNameHints: [String]
    ) async throws -> [TrustedHealthSample] {
        guard let sleepType = HKObjectType.categoryType(forIdentifier: .sleepAnalysis) else {
            throw WearableHealthImportError.missingSampleType("sleepAnalysis")
        }
        let predicate = HKQuery.predicateForSamples(withStart: start, end: end)
        let sort = NSSortDescriptor(key: HKSampleSortIdentifierEndDate, ascending: false)
        return try await withCheckedThrowingContinuation { continuation in
            let query = HKSampleQuery(
                sampleType: sleepType,
                predicate: predicate,
                limit: 500,
                sortDescriptors: [sort]
            ) { _, rawSamples, error in
                if let error {
                    continuation.resume(throwing: error)
                    return
                }
                let rows = (rawSamples as? [HKCategorySample] ?? [])
                    .filter { Self.matchesSource($0, hints: sourceNameHints) }
                    .map { sample in
                        Self.healthSample(
                            sample: sample,
                            kind: "sleep-analysis",
                            value: sample.endDate.timeIntervalSince(sample.startDate) / 60.0,
                            unit: "minutes",
                            metadata: ["stage": Self.sleepStageName(sample.value)]
                        )
                    }
                continuation.resume(returning: rows)
            }
            healthStore.execute(query)
        }
    }

    func fetchWorkoutSamples(
        healthStore: HKHealthStore,
        start: Date,
        end: Date,
        sourceNameHints: [String]
    ) async throws -> [TrustedHealthSample] {
        let predicate = HKQuery.predicateForSamples(withStart: start, end: end)
        let sort = NSSortDescriptor(key: HKSampleSortIdentifierEndDate, ascending: false)
        return try await withCheckedThrowingContinuation { continuation in
            let query = HKSampleQuery(
                sampleType: HKObjectType.workoutType(),
                predicate: predicate,
                limit: 200,
                sortDescriptors: [sort]
            ) { _, rawSamples, error in
                if let error {
                    continuation.resume(throwing: error)
                    return
                }
                let rows = (rawSamples as? [HKWorkout] ?? [])
                    .filter { Self.matchesSource($0, hints: sourceNameHints) }
                    .map { workout in
                        var metadata: [String: String] = [
                            "activity-type": "\(workout.workoutActivityType.rawValue)"
                        ]
                        if let energy = workout.totalEnergyBurned?.doubleValue(for: .kilocalorie()) {
                            metadata["active-energy-kcal"] = String(format: "%.2f", energy)
                        }
                        if let distance = workout.totalDistance?.doubleValue(for: .meter()) {
                            metadata["distance-m"] = String(format: "%.2f", distance)
                        }
                        return Self.healthSample(
                            sample: workout,
                            kind: "workout",
                            value: workout.duration / 60.0,
                            unit: "minutes",
                            metadata: metadata
                        )
                    }
                continuation.resume(returning: rows)
            }
            healthStore.execute(query)
        }
    }

    static func matchesSource(_ sample: HKSample, hints: [String]) -> Bool {
        guard !hints.isEmpty else { return true }
        let fields = [
            sample.sourceRevision.source.name,
            sample.sourceRevision.source.bundleIdentifier,
            sample.device?.name,
            sample.device?.manufacturer,
            sample.device?.model,
        ].compactMap { $0 }
        return hints.contains { hint in
            fields.contains { field in field.localizedCaseInsensitiveContains(hint) }
        }
    }

    static func healthSample(
        sample: HKSample,
        kind: String,
        value: Double,
        unit: String,
        metadata: [String: String] = [:]
    ) -> TrustedHealthSample {
        let formatter = ISO8601DateFormatter()
        return TrustedHealthSample(
            id: sample.uuid.uuidString,
            kind: kind,
            value: value,
            unit: unit,
            startDate: formatter.string(from: sample.startDate),
            endDate: formatter.string(from: sample.endDate),
            sourceName: sample.sourceRevision.source.name,
            sourceBundleIdentifier: sample.sourceRevision.source.bundleIdentifier,
            deviceName: sample.device?.name,
            metadata: metadata
        )
    }

    static func sleepStageName(_ value: Int) -> String {
        if value == HKCategoryValueSleepAnalysis.inBed.rawValue { return "in-bed" }
        if value == HKCategoryValueSleepAnalysis.asleep.rawValue { return "asleep" }
        if value == HKCategoryValueSleepAnalysis.awake.rawValue { return "awake" }
        if #available(iOS 16.0, *) {
            if value == HKCategoryValueSleepAnalysis.asleepCore.rawValue { return "asleep-core" }
            if value == HKCategoryValueSleepAnalysis.asleepDeep.rawValue { return "asleep-deep" }
            if value == HKCategoryValueSleepAnalysis.asleepREM.rawValue { return "asleep-rem" }
            if value == HKCategoryValueSleepAnalysis.asleepUnspecified.rawValue { return "asleep-unspecified" }
        }
        return "sleep-stage-\(value)"
    }
}
#endif
