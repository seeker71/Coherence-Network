// order.ts — Order / PartialOrder / TotalOrder structures.
//
// Each structure is a single-constructor INDUCTIVE recipe whose constructor
// packs the carrier, the relation, and the axiom propositions. Built on the
// same shape as Monoid/Group in algebra.ts so the substrate sees the same
// structural pattern.
//
// Axioms surfaced:
//   reflexive    — ∀a. a ≤ a
//   transitive   — ∀a b c. (a ≤ b) ∧ (b ≤ c) ⇒ (a ≤ c)
//   antisymmetric — ∀a b. (a ≤ b) ∧ (b ≤ a) ⇒ (a = b)
//   total        — ∀a b. (a ≤ b) ∨ (b ≤ a)
//
// Order        = (carrier, le, reflexive)
// PartialOrder = (carrier, le, reflexive, transitive, antisymmetric)
// TotalOrder   = PartialOrder + total

import { Kernel, Level, RBasic, type NodeID } from "../kernel.ts";
import { make_constructor, make_inductive } from "../inductive.ts";

function ax(k: Kernel, label: string, op: NodeID): NodeID {
  const head = k.internString(label);
  return k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.FNCALL, inst: 0 },
    [head, op],
  );
}

export const OrderAxioms = {
  reflexive: (k: Kernel, le: NodeID) => ax(k, "reflexive", le),
  transitive: (k: Kernel, le: NodeID) => ax(k, "transitive", le),
  antisymmetric: (k: Kernel, le: NodeID) => ax(k, "antisymmetric", le),
  total: (k: Kernel, le: NodeID) => ax(k, "total", le),
} as const;

export interface OrderCells {
  Order: NodeID;
  PartialOrder: NodeID;
  TotalOrder: NodeID;
}

function placeholder(k: Kernel, name: string): NodeID {
  return k.internString(name);
}

export function buildOrderCells(k: Kernel): OrderCells {
  const carrier_ty = placeholder(k, "carrier");
  const le_ty = placeholder(k, "le");
  const axiom_ty = placeholder(k, "axiom");

  const Order = make_inductive(k, "Order", [], [
    {
      ctor_name: "mk_order",
      ctor_index: 0,
      arg_types: [carrier_ty, le_ty, axiom_ty],
    },
  ]);

  const PartialOrder = make_inductive(k, "PartialOrder", [], [
    {
      ctor_name: "mk_partial_order",
      ctor_index: 0,
      arg_types: [carrier_ty, le_ty, axiom_ty, axiom_ty, axiom_ty],
    },
  ]);

  const TotalOrder = make_inductive(k, "TotalOrder", [], [
    {
      ctor_name: "mk_total_order",
      ctor_index: 0,
      arg_types: [
        carrier_ty, le_ty,
        axiom_ty, axiom_ty, axiom_ty, axiom_ty,
      ],
    },
  ]);

  return { Order, PartialOrder, TotalOrder };
}

export interface OrderInstance {
  readonly cell: NodeID;
  readonly carrier: NodeID;
  readonly le: NodeID;
}

export function make_order(
  k: Kernel,
  cells: OrderCells,
  carrier: NodeID,
  le: NodeID,
): OrderInstance {
  const cell = make_constructor(k, cells.Order, "mk_order", [
    carrier, le,
    OrderAxioms.reflexive(k, le),
  ]);
  return { cell, carrier, le };
}

export function make_partial_order(
  k: Kernel,
  cells: OrderCells,
  carrier: NodeID,
  le: NodeID,
): OrderInstance {
  const cell = make_constructor(k, cells.PartialOrder, "mk_partial_order", [
    carrier, le,
    OrderAxioms.reflexive(k, le),
    OrderAxioms.transitive(k, le),
    OrderAxioms.antisymmetric(k, le),
  ]);
  return { cell, carrier, le };
}

export function make_total_order(
  k: Kernel,
  cells: OrderCells,
  carrier: NodeID,
  le: NodeID,
): OrderInstance {
  const cell = make_constructor(k, cells.TotalOrder, "mk_total_order", [
    carrier, le,
    OrderAxioms.reflexive(k, le),
    OrderAxioms.transitive(k, le),
    OrderAxioms.antisymmetric(k, le),
    OrderAxioms.total(k, le),
  ]);
  return { cell, carrier, le };
}
