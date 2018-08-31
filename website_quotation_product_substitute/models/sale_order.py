# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (c) 2015 Domatix (http://www.domatix.com)
#                       info <email@domatix.com>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from odoo import api, fields, models, _
from itertools import groupby
import odoo.addons.decimal_precision as dp


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    product_substitute_ids = fields.One2many(
        comodel_name='sale.order.substitute',
        inverse_name='order_id',
        string='Substitute Products')

    @api.multi
    def order_lines_layouted(self):
        """
        Returns this order lines classified by sale_layout_category and separated in
        pages according to the category pagebreaks. Used to render the report.
        """
        self.ensure_one()
        report_pages = [[]]
        for category, lines in groupby(self.order_line, lambda l: l.layout_category_id):
            # If last added category induced a pagebreak, this one will be on a new page
            if report_pages[-1] and report_pages[-1][-1]['pagebreak']:
                report_pages.append([])
            # Append category to current report page
            report_pages[-1].append({
                'name': category and category.name or _('Uncategorized'),
                'subtotal': category and category.subtotal,
                'pagebreak': category and category.pagebreak,
                'lines': list(lines)
            })
        return report_pages


class SaleOrderSubstitute(models.Model):
    _name = 'sale.order.substitute'
    _description = 'Substitute Product'

    @api.model
    def default_get(self, fields):
        res = super(SaleOrderSubstitute, self).default_get(fields)
        res['order_id'] = self.env.context.get('kit')
        return res

    @api.depends('product_uom_qty', 'discount', 'price_unit', 'tax_id')
    def _compute_amount(self):
        """
        Compute the amounts of the SO substitute line.
        """
        for line in self:
            price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            taxes = line.tax_id.compute_all(
                price, line.order_id.currency_id, line.product_uom_qty,
                product=line.product_substitute_id,
                partner=line.order_id.partner_shipping_id)
            line.update({
                'price_tax': sum(t.get('amount', 0.0) for t in taxes.get(
                                                                'taxes', [])),
                'price_total': taxes['total_included'],
                'price_subtotal': taxes['total_excluded'],
            })

    sale_order_line_id = fields.Many2one(
        comodel_name='sale.order.line',
        required=True,
        string='Sale Order Line')

    order_id = fields.Many2one(
        comodel_name='sale.order',
        string='Substitute')

    product_substitute_id = fields.Many2one(
        comodel_name='product.product',
        required=True,
        string='Substitute Product')

    description = fields.Char(
        string='Description')

    product_uom_qty = fields.Float(
        string='Quantity',
        digits=dp.get_precision('Product Unit of Measure'),
        required=True,
        default=1.0)

    product_uom = fields.Many2one(
        comodel_name='product.uom',
        string='Unit of Measure',
        related='product_substitute_id.uom_id')

    price_unit = fields.Float(
        string='Price Unit',
        digits=dp.get_precision('Product Price'))

    price_difference = fields.Float(
        string='Price Difference',
        digits=dp.get_precision('Product Price'),
        compute='_compute_price_difference')

    tax_id = fields.Many2many(
        comodel_name='account.tax',
        string='Tax')

    discount = fields.Float(
        string='Discount')

    currency_id = fields.Many2one(related='order_id.currency_id', store=True, string='Currency', readonly=True)
    price_subtotal = fields.Float(
        string='Amount',
        compute='_compute_amount',
        store=True)
    price_tax = fields.Float(compute='_compute_amount', string='Taxes', readonly=True, store=True)
    price_total = fields.Monetary(compute='_compute_amount', string='Total', readonly=True, store=True)

    @api.onchange('sale_order_line_id')
    def _onchange_product_id(self):
        if self.sale_order_line_id.product_id:
            self.product_uom_qty = self.sale_order_line_id.product_uom_qty
            self.description = self.sale_order_line_id.product_id.description_sale or self.sale_order_line_id.product_id.name
            self.price_unit = self.sale_order_line_id.product_id.lst_price
            self.product_uom_qty = self.sale_order_line_id.product_uom_qty
            self.update({'tax_id':self.sale_order_line_id.tax_id.ids})

    @api.onchange('product_substitute_id')
    def _onchange_substitute_product(self):
        self.description = self.product_substitute_id.description_sale or self.product_substitute_id.name
        self.price_unit = self.product_substitute_id.lst_price

    def _compute_price_difference(self):
        for record in self:
            record.price_difference = record.sale_order_line_id.price_unit - record.price_unit

    @api.multi
    def button_substitute_product(self):
        for record in self:
            product_old_id = record.sale_order_line_id.product_id
            price_unit_old = record.sale_order_line_id.price_unit
            quantity_old = record.sale_order_line_id.product_uom_qty
            description_old = record.sale_order_line_id.product_id.description_sale or record.sale_order_line_id.product_id.name
            record.sale_order_line_id.write({'product_id':record.product_substitute_id.id,
                                             'name':record.description,
                                             'price_unit':record.price_unit,
                                             'product_uom_qty':record.product_uom_qty})

            record.write({'product_substitute_id':product_old_id.id,
                          'price_unit':price_unit_old,
                          'product_uom_qty':quantity_old,
                          'description':description_old})

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    substitute_line_ids = fields.One2many(
        comodel_name='sale.order.substitute',
        inverse_name='sale_order_line_id',
        string='Substitute Line ids',
        ondelete='cascade')