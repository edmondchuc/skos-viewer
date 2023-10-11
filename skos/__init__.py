from rdflib.namespace import RDF, SKOS, DCTERMS, RDFS, OWL, DC
from rdflib import URIRef, Namespace, Literal, Graph
import markdown
from flask import url_for
import requests

from config import Config
from skos.concept_scheme import ConceptScheme, ConceptSchemeRenderer
from skos.concept import Concept, ConceptRenderer
from skos.collection import CollectionRenderer, Collection
from skos.register import Register
import helper

from datetime import date
from urllib import parse


# Controlled values
CONCEPT = 0
CONCEPTSCHEME = 1
COLLECTION = 2
METHOD = 3

SCHEMAORG = Namespace('http://schema.org/')


def list_concepts():
    concepts = []
    for c in Config.g.subjects(RDF.type, SKOS.Concept):
        label = get_label(c)
        date_created = get_created_date(c)
        date_modified = get_modified_date(c)
        definition = get_definition(c)
        scheme = get_in_scheme(c)
        concepts.append((c, label, [
            (URIRef('http://purl.org/dc/terms/created'), date_created),
            (URIRef('http://purl.org/dc/terms/modified'), date_modified),
            (URIRef('http://www.w3.org/2004/02/skos/core#definition'), definition),
            (URIRef('http://www.w3.org/2004/02/skos/core#inScheme'), scheme)
        ]))
    return sorted(concepts, key=lambda i: i[1])


def list_concept_schemes():
    concept_schemes = []

    for cc in Config.g.subjects(RDF.type, SKOS.ConceptScheme):
        label = get_label(cc)
        date_created = get_created_date(cc)
        date_modified = get_modified_date(cc)
        description = get_description(cc)
        concept_schemes.append((cc, label, [
            (URIRef('http://purl.org/dc/terms/created'), date_created),
            (URIRef('http://purl.org/dc/terms/modified'), date_modified),
            description
        ]))

    return sorted(concept_schemes, key=lambda i: i[1])


def list_concept_schemes_and_collections():
    items = []

    for cc in Config.g.subjects(RDF.type, SKOS.ConceptScheme):
        if not is_deprecated(cc):
            label = get_label(cc)
            date_created = get_created_date(cc)
            date_modified = get_modified_date(cc)
            description = get_description(cc)
            items.append((cc, label, [
                (URIRef('http://purl.org/dc/terms/created'), date_created),
                (URIRef('http://purl.org/dc/terms/modified'), date_modified),
                description
            ]))

    for cc in Config.g.subjects(RDF.type, SKOS.Collection):
        if not is_deprecated(cc):
            label = get_label(cc)
            date_created = get_created_date(cc)
            date_modified = get_modified_date(cc)
            description = get_description(cc)
            items.append((cc, label, [
                (URIRef('http://purl.org/dc/terms/created'), date_created),
                (URIRef('http://purl.org/dc/terms/modified'), date_modified),
                description
            ]))

    return sorted(items, key=lambda i: i[1])


def _split_camel_case_label(label):
    new_label = ''
    last = 0
    for i, letter in enumerate(label):
        if letter.isupper():
            new_label += ' {}'.format(label[last:i])
            last = i

    new_label += ' {}'.format(label[last:])
    new_label = new_label.strip()
    return new_label


def get_label(uri, create=True):
    # TODO: title() capitalises all words, we need a post-process function to lower case words that are of types
    #       such as preposition and conjunction.
    for label in Config.g.objects(URIRef(uri), SKOS.prefLabel):
        return label
    for label in Config.g.objects(URIRef(uri), DCTERMS.title):
        return label
    for label in Config.g.objects(URIRef(uri), RDFS.label):
        return label

    # Fetch label by dereferencing URI.
    if create:
        headers = {'accept': 'text/turtle'}
        response_g = Graph()
        try:
            r = requests.get(uri, headers=headers)
            assert 200 <= r.status_code < 300
            response_g.parse(data=r.content.decode('utf-8'), format='turtle')
            for _, _, label in response_g.triples((uri, SKOS.prefLabel, None)):
                return label
            for _, _, label in response_g.triples((uri, RDFS.label, None)):
                return label
        except Exception as e:
            # print(uri)
            # print('Error dereferencing external URI:', str(e))
            # print(r.content.decode('utf-8'))
            # print('Create label from the local name of the URI instead.')

            # Create label out of the local segment of the URI.
            label = helper.uri_label(uri)
            label = _split_camel_case_label(label)
            return Literal(label)
    else:
        return Literal(str(uri).split('#')[-1].split('/')[-1])


def get_description(uri):
    for description in Config.g.objects(URIRef(uri), DCTERMS.description):
        return (DCTERMS.description, description)
    for description in Config.g.objects(URIRef(uri), DC.description):
        return (DC.description, description)
    for description in Config.g.objects(URIRef(uri), RDFS.comment):
        return (RDFS.comment, description)


def get_definition(uri):
    for definition in Config.g.objects(URIRef(uri), SKOS.definition):
        return definition


def get_class_types(uri):
    types = []
    for type in Config.g.objects(URIRef(uri), RDF.type):
        # Only add URIs (and not blank nodes!)
        if str(type)[:4] == 'http' \
                and str(type) != 'http://www.w3.org/2004/02/skos/core#ConceptScheme' \
                and str(type) != 'http://www.w3.org/2004/02/skos/core#Concept' \
                and str(type) != 'http://www.w3.org/2004/02/skos/core#Collection':
            types.append(type)
    return types


def is_deprecated(uri):
    for value in Config.g.objects(URIRef(uri), OWL.deprecated):
        return bool(value)
    return False


def get_narrowers(uri):
    narrowers = []
    for narrower in Config.g.objects(URIRef(uri), SKOS.narrower):
        if not is_deprecated(narrower):
            label = get_label(narrower)
            narrowers.append((narrower, label))
    return sorted(narrowers, key=lambda i: i[1])


def get_broaders(uri):
    broaders = []
    for broader in Config.g.objects(URIRef(uri), SKOS.broader):
        if not is_deprecated(broader):
            label = get_label(broader)
            broaders.append((broader, label))
    return sorted(broaders, key=lambda i: i[1])


def get_members(uri):
    members = []
    for member in Config.g.objects(URIRef(uri), SKOS.member):
        label = get_label(member)
        members.append((member, label))
    return sorted(members, key=lambda i: i[1])


def get_top_concept_of(uri):
    top_concept_ofs = []
    for tco in Config.g.objects(URIRef(uri), SKOS.topConceptOf):
        label = get_label(tco)
        top_concept_ofs.append((tco, label))
    return sorted(top_concept_ofs, key=lambda i: i[1])


def get_top_concepts(uri):
    top_concepts = []
    for tc in Config.g.objects(URIRef(uri), SKOS.hasTopConcept):
        label = get_label(tc)
        top_concepts.append((tc, label))
    return sorted(top_concepts, key=lambda i: i[1])


def get_change_note(uri):
    for cn in Config.g.objects(URIRef(uri), SKOS.changeNote):
        return cn


def get_alt_labels(uri):
    labels = []
    for alt_label in Config.g.objects(URIRef(uri), SKOS.altLabel):
        labels.append(alt_label)
    return sorted(labels)


def get_created_date(uri):
    for created in Config.g.objects(URIRef(uri), DCTERMS.created):
        created = created.split('-')
        created = date(int(created[0]), int(created[1]), int(created[2][:2]))
        return created


def get_modified_date(uri):
    for modified in Config.g.objects(URIRef(uri), DCTERMS.modified):
        modified = modified.split('-')
        modified = date(int(modified[0]), int(modified[1]), int(modified[2][:2]))
        return modified


def get_uri_skos_type(uri):
    uri = parse.unquote_plus(uri)
    for _ in Config.g.triples((URIRef(uri), RDF.type, URIRef('https://w3id.org/tern/ontologies/tern/Method'))):
        return METHOD
    for _ in Config.g.triples((URIRef(uri), RDF.type, SKOS.ConceptScheme)):
        return CONCEPTSCHEME
    for _ in Config.g.triples((URIRef(uri), RDF.type, SKOS.Concept)):
        return CONCEPT
    for _ in Config.g.triples((URIRef(uri), RDF.type, SKOS.Collection)):
        return COLLECTION
    return None


def get_properties(uri):
    ignore = [
        # Common
        RDF.type, SKOS.prefLabel, DCTERMS.title, RDFS.label, DCTERMS.description, SKOS.definition, SKOS.changeNote,
        DCTERMS.created, DCTERMS.modified, OWL.sameAs, RDFS.comment, SKOS.altLabel, DCTERMS.bibliographicCitation,
        RDFS.isDefinedBy, DC.description, DCTERMS.creator, DCTERMS.contributor, SCHEMAORG.parentOrganization,
        SCHEMAORG.contactPoint, SCHEMAORG.member, SCHEMAORG.subOrganization, SCHEMAORG.familyName,
        URIRef('http://schema.semantic-web.at/ppt/propagateType'), SCHEMAORG.givenName, SCHEMAORG.honorificPrefix,
        SCHEMAORG.jobTitle, SCHEMAORG.memberOf, URIRef('http://schema.semantic-web.at/ppt/appliedType'), SKOS.member,

        # Concept
        SKOS.narrower, SKOS.broader, SKOS.topConceptOf, SKOS.inScheme, SKOS.closeMatch, SKOS.exactMatch,

        # Concept Scheme
        SKOS.hasTopConcept
    ]

    properties = []
    for _, property, value in Config.g.triples((URIRef(uri), None, None)):
        if property in ignore:
            continue

        label = get_label(value, create=False) if type(value) == URIRef else None
        properties.append(((property, get_label(property, create=False)), value, label))

    properties.sort(key=lambda x: x[0])
    return properties


def get_in_scheme(uri):
    """A concept scheme in which the concept is a part of. A concept may be a member of more than one concept scheme"""
    schemes = []
    for scheme in Config.g.objects(URIRef(uri), SKOS.inScheme):
        label = get_label(scheme)
        schemes.append((scheme, label))
    return schemes


def _add_narrower(uri, hierarchy, indent):
    concepts = []

    for concept in Config.g.objects(URIRef(uri), SKOS.narrower):
        if not is_deprecated(concept):
            label = get_label(concept)
            concepts.append((concept, label))

    for concept in Config.g.objects(URIRef(uri), SKOS.member):
        if not is_deprecated(concept):
            label = get_label(concept)
            concepts.append((concept, label))

    concepts.sort(key=lambda i: i[1])

    for concept in concepts:
        tab = indent * '\t'
        hierarchy += tab + '- [{}]({})\n'.format(concept[1], url_for('routes.ob', uri=concept[0]))
        hierarchy = _add_narrower(concept[0], hierarchy, indent + 1)

    return hierarchy


def get_concept_hierarchy_collection(uri):
    hierarchy = ''
    members = []

    for concept_or_collection in Config.g.objects(URIRef(uri), SKOS.member):
        if not is_deprecated(concept_or_collection):
            label = get_label(concept_or_collection)
            members.append((concept_or_collection, label))

    members.sort(key=lambda i: i[1])

    for member in members:
        hierarchy += '- [{}]({})\n'.format(member[1], url_for('routes.ob', uri=member[0]))
        hierarchy = _add_narrower(member[0], hierarchy, 1)

    return '<div id="concept-hierarchy">' + markdown.markdown(hierarchy) + '</div>'


def get_concept_hierarchy(uri):
    hierarchy = ''
    top_concepts = []
    for top_concept in Config.g.objects(URIRef(uri), SKOS.hasTopConcept):
        if not is_deprecated(top_concept):
            label = get_label(top_concept)
            top_concepts.append((top_concept, label))

    top_concepts.sort(key=lambda i: i[1])

    for top_concept in top_concepts:
        hierarchy += '- [{}]({})\n'.format(top_concept[1], url_for('routes.ob', uri=top_concept[0]))
        hierarchy = _add_narrower(top_concept[0], hierarchy, 1)
    return '<div id="concept-hierarchy">' + markdown.markdown(hierarchy) + '</div>'


def get_is_defined_by(uri):
    for is_def in Config.g.objects(URIRef(uri), RDFS.isDefinedBy):
        return is_def


def get_close_match(uri):
    close_match = []
    for cm in Config.g.objects(URIRef(uri), SKOS.closeMatch):
        close_match.append(cm)
    return close_match


def get_exact_match(uri):
    exact_match = []
    for em in Config.g.objects(URIRef(uri), SKOS.exactMatch):
        exact_match.append(em)
    return exact_match


def get_bibliographic_citation(uri):
    for bg in Config.g.objects(URIRef(uri), DCTERMS.bibliographicCitation):
        return bg


def get_dcterms_source(uri):
    for _, _, source in Config.g.triples((URIRef(uri), DCTERMS.source, None)):
        return source


def get_schema_org_parent_org(uri):
    for parent_org in Config.g.objects(URIRef(uri), SCHEMAORG.parentOrganization):
        label = get_label(parent_org)
        return (parent_org, label)


def get_schema_org_contact_point(uri):
    for cp in Config.g.objects(URIRef(uri), SCHEMAORG.contactPoint):
        label = get_label(cp)
        return (cp, label)


def get_schema_org_members(uri):
    members = []
    for m in Config.g.objects(URIRef(uri), SCHEMAORG.member):
        label = get_label(m)
        members.append((m, label))
    return members


def get_schema_org_sub_orgs(uri):
    orgs = []
    for org in Config.g.objects(URIRef(uri), SCHEMAORG.subOrganization):
        label = get_label(org)
        orgs.append((org, label))
    return orgs


def get_schema_org_family_name(uri):
    for fn in Config.g.objects(URIRef(uri), SCHEMAORG.familyName):
        return fn


def get_schema_org_given_name(uri):
    for gn in Config.g.objects(URIRef(uri), SCHEMAORG.givenName):
        return gn


def get_schema_org_honorific_prefix(uri):
    for hp in Config.g.objects(URIRef(uri), SCHEMAORG.honorificPrefix):
        return hp


def get_schema_org_job_title(uri):
    for jt in Config.g.objects(URIRef(uri), SCHEMAORG.jobTitle):
        return jt


def get_schema_org_member_of(uri):
    for org in Config.g.objects(URIRef(uri), SCHEMAORG.memberOf):
        label = get_label(org)
        return (org, label)


def member_of(uri):
    """
    The inverse of skos:member - used for better UI navigation.
    """
    collections = []
    for collection in Config.g.subjects(SKOS.member, URIRef(uri)):
        label = get_label(collection)
        collections.append((collection, label))
    return collections

def subjects(uri):
    """
    which subjects are in scheme?
    """
    subjects = []
    for sj in Config.g.subjects(SKOS.inScheme, URIRef(uri)):
        label = get_label(sj)
        subjects.append((sj, label))
    return subjects


def get_creator(uri):
    for creator in Config.g.objects(URIRef(uri), DCTERMS.creator):
        return creator


def get_rdf_predicate(uri):
    for predicate in Config.g.objects(URIRef(uri), RDF.predicate):
        return predicate


def get_rdf_object(uri):
    for o in Config.g.objects(URIRef(uri), RDF.object):
        return o


def get_mapping_statement(uri):
    uri = URIRef(uri)
    for statement in Config.g.subjects(RDF.type, RDF.Statement):
        for _, p, o in Config.g.triples((statement, None, None)):
            if p == RDF.subject and o == uri:
                return [
                    statement,
                    get_rdf_predicate(statement),
                    get_rdf_object(statement),
                    get_created_date(statement),
                    get_creator(statement),
                    get_description(statement)[1],
                ]


def get_method_purpose(uri):
    uri = URIRef(uri)
    for _, _, purpose in Config.g.triples((uri, URIRef('https://w3id.org/tern/ontologies/tern/purpose'), None)):
        return purpose


def get_method_scope(uri):
    uri = URIRef(uri)
    for _, _, scope in Config.g.triples((uri, URIRef('https://w3id.org/tern/ontologies/tern/scope'), None)):
        return scope


def get_method_equipment(uri):
    uri = URIRef(uri)
    equipments = []
    for _, _, equipment in Config.g.triples((uri, URIRef('https://w3id.org/tern/ontologies/tern/equipment'), None)):
        if isinstance(equipment, URIRef):
            label = get_label(equipment)
            equipments.append((equipment, label))
        else:
            return equipment
    return equipments


def get_method_instructions(uri):
    uri = URIRef(uri)
    for _, _, instructions in Config.g.triples((uri, URIRef('https://w3id.org/tern/ontologies/tern/instructions'), None)):
        return instructions


def get_parameter_relations(uri):
    uri = URIRef(uri)
    parameters = []
    for _, _, parameter in Config.g.triples((uri, URIRef('https://w3id.org/tern/ontologies/tern/hasParameter'), None)):
        label = get_label(parameter)
        parameters.append((parameter, label))

    return parameters


def get_categorical_variables_relations(uri):
    uri = URIRef(uri)
    cvs = []
    for _, _, cv in Config.g.triples((uri, URIRef('https://w3id.org/tern/ontologies/tern/hasCategoricalVariableCollection'), None)):
        label = get_label(cv)
        cvs.append((cv, label))

    return cvs


def get_method_time_required(uri):
    uri = URIRef(uri)
    for _, _, time_required in Config.g.triples((uri, URIRef('http://schema.org/timeRequired'), None)):
        return time_required


def get_method_additional_note(uri):
    uri = URIRef(uri)
    for _, _, note in Config.g.triples((uri, SKOS.note, None)):
        return note
