from odoo import api, fields, models

from odoo.addons.http_routing.models.ir_http import slugify


class HelpdeskCategory(models.Model):
    _inherit = "helpdesk.ticket.category"
    _rec_name = "complete_name"

    _parent_store = True
    _parent_name = "parent_id"

    parent_id = fields.Many2one(
        string="Parent",
        comodel_name="helpdesk.ticket.category",
        index=True,
        ondelete="cascade",
    )
    parent_path = fields.Char(index=True)
    child_ids = fields.One2many(
        string="Sub-types",
        comodel_name="helpdesk.ticket.category",
        inverse_name="parent_id",
    )

    complete_name = fields.Char(
        string="Complete Name", compute="_compute_complete_name", store=True
    )

    code = fields.Char(
        string="Code",
        compute="_compute_code",
        readonly=False,
        inverse="_inverse_code",
        store=True,
        index=True,
    )

    tickets_count = fields.Integer(string="# Tickets", compute="_compute_tickets_count")

    #
    # Copute fields

    @api.depends("name", "parent_id.complete_name")
    def _compute_complete_name(self):
        for r in self:
            if r.parent_id:
                r.complete_name = "%s / %s" % (r.parent_id.complete_name, r.name)
            else:
                r.complete_name = r.name

    @api.depends("parent_id", "name", "code")
    def _compute_code(self):
        for r in self:
            if r.name and r.name.strip():
                parent_code = f"{r.parent_id.code}-" if r.parent_id else ""
                r.code = "{}{}".format(parent_code, slugify(r.name))
            else:
                r.code = False

    def _inverse_code(self):
        for r in self:
            r.code = slugify(r.code)

    def no_compute_tickets_count(self):
        """
        TODO: speed up
        Count tickets accumulated in subcategories
        >>> env['helpdesk.ticket'].search_count([('category_id','child_of', 9)])
        SELECT count(1) FROM "helpdesk_ticket"
        WHERE (
            ("helpdesk_ticket"."active" = true)
            AND (
                "helpdesk_ticket"."category_id" in (
                    SELECT "helpdesk_ticket_category".id FROM "helpdesk_ticket_category"
                    WHERE (
                        ("helpdesk_ticket_category"."active" = true)
                        AND
                        ("helpdesk_ticket_category"."parent_path"::text like '7/3/8/9/%')
                    )
                )
            )
        )
        """
        category_tickets_count = {}
        if self.ids:
            self.env.cr.execute(
                """SELECT category_id, COUNT(*)
                FROM helpdesk_ticket
                WHERE category_id in %s
                GROUP BY category_id""",
                (tuple(self.ids),),
            )
            category_tickets_count = dict(self.env.cr.fetchall())
        for r in self:
            r.tickets_count = category_tickets_count.get(r.id, 0)

    def _compute_tickets_count(self):
        HelpdeskTicket = self.env["helpdesk.ticket"]
        for r in self:
            r.tickets_count = (
                HelpdeskTicket.search_count([("category_id", "child_of", r.id)]) or 0
            )
